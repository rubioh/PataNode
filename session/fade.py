"""Eased parameter transitions between session states.

A hard cut snaps every parameter at once. A fade eases a chosen few over a
duration instead, so arriving at a state reads as a move rather than a jump.

The whole thing rests on one existing fact: a GPU parameter in PataNode is
not a number, it is a *string expression* that
ProgramBase.getAdaptableEvaluationForUniform (program/program_base.py:439)
eval()s every frame with `x` bound to the base attribute, then float()s.
So interpolating needs no new evaluation machinery and no extra render
pull -- writing "(1-0.37)*(x*2)+(0.37)*(.9)" into that slot *is* the fade,
and the per-frame bindUniformToProgram picks it up on its own. It also
means an audio-driven expression fades exactly like a plain literal, and a
malformed side degrades to a hard cut through the existing except-clause
fallback rather than raising into the 60 Hz audio timer.

A fade lives on the state it fades *into* -- "when the session arrives
here, ease these in" -- so it survives reordering and works no matter which
state you jumped from.

Pure data: no Qt, no GL, no scene.
"""

from session.propagation import values_for_kind

DEFAULT_DURATION = 1.0
DEFAULT_CURVE = "smoothstep"

CURVES = {
    "linear": lambda a: a,
    "smoothstep": lambda a: a * a * (3.0 - 2.0 * a),
}

# How many times a fade may be interrupted before it stops nesting the live
# half-blended expression and snaps to the previous target instead. Each
# interruption wraps the whole previous expression as the new `old` side,
# which is what makes an interrupted transition seamless -- but mashing Next
# would otherwise grow the string without bound.
MAX_NESTING = 4


def ease(a: float, curve: str = DEFAULT_CURVE) -> float:
    a = min(1.0, max(0.0, a))
    return CURVES.get(curve, CURVES["linear"])(a)


def blend_expression(old: str, new: str, a: float) -> str:
    """The expression that reads as `old` at a=0 and `new` at a=1.

    Both sides are parenthesised because either may be compound: `old` is
    routinely something like "x*2", and an unparenthesised 1-a*x*2 is a
    different number entirely.
    """
    return "(1-%r)*(%s)+(%r)*(%s)" % (a, old, a, new)


def is_blendable(value) -> bool:
    """Whether a stored parameter value can sit inside a blend expression.

    A missing or blank expression would make the synthesized string a
    syntax error, which the eval fallback would silently turn into a hard
    cut -- better to never offer it in the first place.
    """
    return isinstance(value, str) and value.strip() != ""


class FadeParam:
    """One parameter to ease, and optionally what to ease it between.

    `from_value` None means "read the parameter's live value when the
    switch happens" -- that is what makes a fade independent of which state
    you arrived from. `to_value` None means "use the target state's stored
    value". Setting either explicitly is the Blend-node case: both states
    store baseBlend 0.5 and the transition itself sweeps it 0 -> 1.
    """

    def __init__(self, node_id, program, uniform, from_value=None, to_value=None):
        self.node_id = node_id
        self.program = program
        self.uniform = uniform
        self.from_value = from_value
        self.to_value = to_value

    @property
    def key(self):
        return (self.node_id, self.program, self.uniform)

    def to_dict(self) -> dict:
        data = {
            "node_id": self.node_id,
            "program": self.program,
            "uniform": self.uniform,
        }
        # Omit the nulls: they are the common case, and a fade block full of
        # "from": null noise is harder to hand-edit.
        if self.from_value is not None:
            data["from"] = self.from_value
        if self.to_value is not None:
            data["to"] = self.to_value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "FadeParam":
        return cls(
            node_id=data["node_id"],
            program=data["program"],
            uniform=data["uniform"],
            from_value=data.get("from"),
            to_value=data.get("to"),
        )

    def __eq__(self, other):
        return isinstance(other, FadeParam) and vars(self) == vars(other)

    def __repr__(self):
        return "<FadeParam node=%s %s.%s %r -> %r>" % (
            self.node_id,
            self.program,
            self.uniform,
            self.from_value,
            self.to_value,
        )


class FadeSpec:
    """What a state's `fade` block says: how long, what shape, which params."""

    def __init__(self, duration=DEFAULT_DURATION, curve=DEFAULT_CURVE, params=None):
        self.duration = duration
        self.curve = curve
        self.params = params if params is not None else []

    def to_dict(self) -> dict:
        return {
            "duration": self.duration,
            "curve": self.curve,
            "params": [param.to_dict() for param in self.params],
        }

    @classmethod
    def from_dict(cls, data):
        """None in, None out -- a state without a fade has no fade."""
        if not data:
            return None
        return cls(
            duration=data.get("duration", DEFAULT_DURATION),
            curve=data.get("curve", DEFAULT_CURVE),
            params=[FadeParam.from_dict(p) for p in data.get("params", [])],
        )

    def __eq__(self, other):
        return (
            isinstance(other, FadeSpec)
            and self.duration == other.duration
            and self.curve == other.curve
            and self.params == other.params
        )

    def __repr__(self):
        return "<FadeSpec %ss %s %d param(s)>" % (
            self.duration,
            self.curve,
            len(self.params),
        )


class ResolvedFade:
    """One parameter mid-fade, with both endpoints already pinned down.

    `depth` counts how many interruptions deep this expression is nested;
    SessionPlayer uses it against MAX_NESTING.
    """

    def __init__(self, node_id, program, uniform, old, new, depth=0):
        self.node_id = node_id
        self.program = program
        self.uniform = uniform
        self.old = old
        self.new = new
        self.depth = depth

    @property
    def key(self):
        return (self.node_id, self.program, self.uniform)

    def value_at(self, a: float) -> str:
        return blend_expression(self.old, self.new, a)


class ActiveFade:
    """A fade in flight: the resolved endpoints plus a clock."""

    def __init__(self, entries, duration, curve, start):
        self.entries = entries
        self.duration = duration
        self.curve = curve
        self.start = start

    def progress(self, now: float) -> float:
        """Eased 0..1. A non-positive duration lands on 1 immediately."""
        if self.duration <= 0:
            return 1.0
        return ease((now - self.start) / self.duration, self.curve)

    def is_done(self, now: float) -> bool:
        return self.duration <= 0 or (now - self.start) >= self.duration


def fade_candidates(prev_scene: dict, next_scene: dict) -> list:
    """Every GPU uniform that could be faded between two scene snapshots.

    Only nodes present in *both* scenes: the union model keeps every node
    resident, so a node missing from one side has no meaningful "from" or
    "to" value to ease between.

    Every uniform of every common node is offered, not only the ones that
    differ. A Blend node routinely stores the same baseBlend in both states
    -- what changes is the wiring -- and sweeping it is exactly what makes
    the transition a crossfade. `differs` marks the ones the GUI
    pre-selects.

    CPU parameters are excluded on purpose: they are read as raw strings
    with no eval (ProgramBase.getSingleCpuParameters), so a blend
    expression would reach the consumer as literal text.
    """
    prev_nodes = {node["id"]: node for node in prev_scene.get("nodes", [])}

    candidates = []
    for next_node in next_scene.get("nodes", []):
        prev_node = prev_nodes.get(next_node["id"])
        if prev_node is None:
            continue

        params = []
        for program, uniform, new_value in values_for_kind(next_node, "gpu"):
            old_value = _lookup(prev_node, program, uniform)
            if not (is_blendable(old_value) and is_blendable(new_value)):
                continue
            params.append(
                {
                    "program": program,
                    "uniform": uniform,
                    "from": old_value,
                    "to": new_value,
                    "differs": old_value != new_value,
                }
            )

        if params:
            candidates.append(
                {
                    "node_id": next_node["id"],
                    "title": next_node.get("title", "<untitled>"),
                    "params": params,
                }
            )

    return candidates


def _lookup(node: dict, program: str, uniform: str):
    spec = (
        (node.get("gpu_adaptable_parameters", {}) or {}).get(program, {}).get(uniform)
    )
    if spec is None:
        return None
    return spec.get("eval_function", {}).get("value")
