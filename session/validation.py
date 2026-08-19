"""Static validation of a live session.

Pure: takes the registry contents as arguments rather than importing them,
so it needs neither the node registry nor a GL context.

Every problem in the session is collected in one pass. Instantiation and
GLSL-compile failures are not detectable here -- SessionPlayer.load appends
those.
"""

from session.fade import CURVES
from session.trigger import COUNTER_FEATURES


class Finding:
    def __init__(self, state_index: int, category: str, message: str):
        self.state_index = state_index
        self.category = category
        self.message = message

    def __repr__(self):
        return "<Finding state=%d %s: %s>" % (
            self.state_index,
            self.category,
            self.message,
        )

    def __eq__(self, other):
        return (
            isinstance(other, Finding)
            and self.state_index == other.state_index
            and self.category == other.category
            and self.message == other.message
        )


def validate_session(session, known_opcodes: set, known_features: set) -> list:
    findings = []

    for index, state in enumerate(session.states):
        findings.extend(_validate_nodes(index, state, known_opcodes))
        findings.extend(_validate_edges(index, state))
        findings.extend(_validate_trigger(index, state, known_features))
        findings.extend(_validate_fade(index, state))

    return findings


def _validate_nodes(index, state, known_opcodes):
    findings = []
    for node in state.scene.get("nodes", []):
        if "op_code" not in node:
            findings.append(
                Finding(
                    index,
                    "node",
                    "Node '%s' has no op_code and cannot be rebuilt"
                    % node.get("title", "<untitled>"),
                )
            )
        elif node["op_code"] not in known_opcodes:
            findings.append(
                Finding(
                    index,
                    "node",
                    "Node '%s' uses unregistered op_code %s"
                    % (node.get("title", "<untitled>"), node["op_code"]),
                )
            )
    return findings


def _validate_edges(index, state):
    socket_ids = set()
    for node in state.scene.get("nodes", []):
        for socket in node.get("inputs", []) + node.get("outputs", []):
            socket_ids.add(socket["id"])

    findings = []
    for edge in state.scene.get("edges", []):
        for end in ("start", "end"):
            if edge.get(end) not in socket_ids:
                findings.append(
                    Finding(
                        index,
                        "edge",
                        "Edge %s references a %s socket that no node provides"
                        % (edge.get("id", "<unknown>"), end),
                    )
                )
    return findings


def _validate_trigger(index, state, known_features):
    trigger = state.trigger or {}

    if trigger.get("type") == "time":
        return _validate_time_trigger(index, trigger)

    if trigger.get("type") != "audio":
        return []

    feature = trigger.get("feature")
    if feature not in known_features:
        return [
            Finding(
                index,
                "trigger",
                "Trigger uses unknown audio feature '%s'" % feature,
            )
        ]

    if "count" in trigger and feature not in COUNTER_FEATURES:
        return [
            Finding(
                index,
                "trigger",
                "Trigger counts on '%s', which is not a counter. "
                "Only %s can be counted." % (feature, ", ".join(COUNTER_FEATURES)),
            )
        ]

    # An audio trigger must be either a counter ("count") or a threshold
    # ("above" + "hold") -- trigger.py:evaluate_trigger only knows those two
    # shapes. Neither present means the trigger never advances (silently
    # stuck mid-set); "above" without "hold" means trigger.py:62 does
    # trigger["hold"] and raises KeyError straight into the 60 Hz audio
    # timer (SessionPlayer.tick -> app.py:122).
    if "count" not in trigger and "above" not in trigger:
        return [
            Finding(
                index,
                "trigger",
                "Audio trigger has neither 'count' nor 'above' and will never advance",
            )
        ]

    if "above" in trigger and "hold" not in trigger:
        return [
            Finding(
                index,
                "trigger",
                "Threshold trigger on '%s' is missing 'hold'" % feature,
            )
        ]

    return []


def _validate_time_trigger(index, trigger):
    """A timer must carry a positive duration.

    Missing: trigger.py reads trigger["seconds"] unguarded, so the state
    never advances (SessionPlayer.tick's KeyError guard) and silently
    strands the set. Zero or negative: the elapsed check is true on the
    first tick, flipping states at 60 Hz.
    """
    if "seconds" not in trigger:
        return [
            Finding(index, "trigger", "Timer trigger is missing 'seconds'"),
        ]

    seconds = trigger["seconds"]
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        return [
            Finding(
                index,
                "trigger",
                "Timer trigger's 'seconds' is %r, which is not a number" % (seconds,),
            )
        ]

    if seconds <= 0:
        return [
            Finding(
                index,
                "trigger",
                "Timer trigger lasts %g seconds; it must be greater than 0" % seconds,
            )
        ]

    return []


def _validate_fade(index, state):
    """A fade that points at nothing would silently do nothing at runtime.

    SessionPlayer._start_fade skips any param it cannot resolve rather than
    raising into the 60 Hz audio timer, so a stale node id after an edit
    turns into a transition that just looks like it forgot to fade. Say so
    at load time instead.
    """
    fade = getattr(state, "fade", None)
    if fade is None:
        return []

    findings = []

    if not isinstance(fade.duration, (int, float)) or fade.duration <= 0:
        findings.append(
            Finding(
                index,
                "fade",
                "Fade duration %r is not a positive number" % (fade.duration,),
            )
        )

    if fade.curve not in CURVES:
        findings.append(
            Finding(
                index,
                "fade",
                "Fade uses unknown curve '%s'. Known curves: %s"
                % (fade.curve, ", ".join(sorted(CURVES))),
            )
        )

    nodes = {node["id"]: node for node in state.scene.get("nodes", [])}
    for param in fade.params:
        node = nodes.get(param.node_id)
        if node is None:
            findings.append(
                Finding(
                    index,
                    "fade",
                    "Fade targets node %s, which this state does not contain"
                    % param.node_id,
                )
            )
            continue

        uniforms = (node.get("gpu_adaptable_parameters", {}) or {}).get(
            param.program, {}
        )
        if param.uniform not in uniforms:
            findings.append(
                Finding(
                    index,
                    "fade",
                    "Fade targets '%s.%s' on node '%s', which does not declare it"
                    % (param.program, param.uniform, node.get("title", "<untitled>")),
                )
            )

    return findings
