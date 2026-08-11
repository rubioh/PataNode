"""The fade runtime: SessionPlayer easing parameters instead of snapping them.

Uses a stand-in node rather than a real ShaderNode, which would need a GL
context and a compiled shader. It reproduces exactly the two pieces of the
ShaderNode contract the runtime touches -- getGpuAdaptableParameters() for
reading and program.setAdaptableParameters() for writing -- so a change to
either on the real class shows up here as a failure.
"""

import copy

import pytest

from nodeeditor.node_node import Node
from session.fade import MAX_NESTING, FadeParam, FadeSpec
from session.model import LiveSession, SessionState
from session.player import SessionPlayer

OPCODES = {100}
FEATURES = {"kick_count"}


class FakeProgram:
    def __init__(self):
        self.adaptable_parameters_dict = {}

    def setAdaptableParameters(self, program_name, uniform_name, params, value):
        self.adaptable_parameters_dict[program_name][uniform_name][params][
            "value"
        ] = value


class FakeShaderNode(Node):
    """Plain Node plus the GPU-parameter surface ShaderNode exposes."""

    def __init__(self, scene):
        super().__init__(scene, "Fake")
        self.program = FakeProgram()

    def getGpuAdaptableParameters(self):
        return self.program.adaptable_parameters_dict

    def deserialize(self, data, hashmap={}, restore_id=True, *args, **kwargs):
        res = super().deserialize(data, hashmap, restore_id, *args, **kwargs)
        self.program.adaptable_parameters_dict = copy.deepcopy(
            data.get("gpu_adaptable_parameters", {})
        )
        return res

    def serialize(self):
        res = super().serialize()
        res["gpu_adaptable_parameters"] = copy.deepcopy(
            self.program.adaptable_parameters_dict
        )
        return res


def node(nid, uniforms, outputs=(), inputs=()):
    return {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": 100,
        "inputs": [
            {
                "id": sid,
                "index": i,
                "multi_edges": False,
                "position": 2,
                "socket_type": 1,
            }
            for i, sid in enumerate(inputs)
        ],
        "outputs": [
            {
                "id": sid,
                "index": i,
                "multi_edges": True,
                "position": 5,
                "socket_type": 1,
            }
            for i, sid in enumerate(outputs)
        ],
        "content": {},
        "gpu_adaptable_parameters": {
            "program": {
                name: {"eval_function": {"value": value}}
                for name, value in uniforms.items()
            }
        },
    }


def make_scene(nodes, edges=()):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes),
        "edges": list(edges),
    }


def live_value(player, node_id, uniform="speed"):
    node_obj = next(n for n in player.scene.nodes if n.id == node_id)
    return node_obj.getGpuAdaptableParameters()["program"][uniform]["eval_function"][
        "value"
    ]


def evaluate(expression, x=1.0):
    """ProgramBase.getAdaptableEvaluationForUniform's semantics."""
    try:
        return float(eval(expression))
    except Exception:
        return x


def build(scene, fade=None, uniform_values=("0", "1"), duration=2.0):
    """Two states differing only in one uniform, the second optionally faded."""
    old, new = uniform_values
    session = LiveSession(
        states=[
            SessionState(
                "a", {"type": "manual"}, make_scene([node(1, {"speed": old})])
            ),
            SessionState(
                "b",
                {"type": "manual"},
                make_scene([node(1, {"speed": new})]),
                fade=fade,
            ),
        ]
    )
    if fade is not None:
        fade.duration = duration
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)
    return player


@pytest.fixture
def shader_scene(scene):
    scene.setNodeClassSelector(lambda data: FakeShaderNode)
    return scene


@pytest.fixture
def faded(shader_scene):
    spec = FadeSpec(2.0, "linear", [FadeParam(1, "program", "speed")])
    player = build(shader_scene, fade=spec)
    player.goTo(0)
    return player


# -- the basic lifecycle --------------------------------------------------


def test_without_a_fade_the_switch_still_hard_cuts(shader_scene):
    """Every existing session must behave exactly as it did before."""
    player = build(shader_scene)
    player.goTo(0)
    player.goTo(1)
    assert live_value(player, 1) == "1"


def test_the_first_frame_shows_the_outgoing_value(faded):
    """_start_fade writes a=0 immediately rather than waiting for the first
    tick -- otherwise the incoming value flashes for one frame, which is the
    exact pop the feature exists to remove."""
    faded.goTo(1)
    assert evaluate(live_value(faded, 1)) == pytest.approx(0.0)


def test_it_eases_through_the_middle(faded):
    faded.goTo(1)
    faded.tick({}, 100.0)  # anchors the clock
    faded.tick({}, 100.5)

    assert evaluate(live_value(faded, 1)) == pytest.approx(0.25)


def test_it_lands_on_the_exact_target_string_not_a_blend(faded):
    """The last write has to be the state's own expression. Leaving a
    blend expression behind at a=1 would be numerically right but would get
    serialized verbatim by the next Capture."""
    faded.goTo(1)
    faded.tick({}, 100.0)
    faded.tick({}, 103.0)

    assert live_value(faded, 1) == "1"
    assert faded._active_fade is None


def test_the_clock_anchors_on_the_first_tick_not_at_goto(faded):
    """self._now is only as fresh as the last audio tick, and is 0.0 before
    any tick has run. Anchoring there would make the first real tick see an
    elapsed time of "since the epoch" and snap the fade shut instantly."""
    faded.goTo(1)
    faded.tick({}, 5000.0)
    assert evaluate(live_value(faded, 1)) == pytest.approx(0.0)

    faded.tick({}, 5001.0)
    assert evaluate(live_value(faded, 1)) == pytest.approx(0.5)


def test_a_fade_runs_while_paused(faded):
    """tick() returns early when not playing, but manual Next always works,
    so the fade advance has to sit before that guard."""
    faded.goTo(1)
    assert not faded.is_playing

    faded.tick({}, 100.0)
    faded.tick({}, 101.0)
    assert evaluate(live_value(faded, 1)) == pytest.approx(0.5)


# -- endpoints ------------------------------------------------------------


def test_an_explicit_from_and_to_sweep_a_parameter_both_states_share(shader_scene):
    """The Blend case: baseBlend is 0.5 in both states and only the wiring
    changes, so the transition itself has to drive it."""
    spec = FadeSpec(
        2.0, "linear", [FadeParam(1, "program", "speed", from_value="0", to_value="1")]
    )
    player = build(shader_scene, fade=spec, uniform_values=("0.5", "0.5"))
    player.goTo(0)
    player.goTo(1)

    assert evaluate(live_value(player, 1)) == pytest.approx(0.0)
    player.tick({}, 100.0)
    player.tick({}, 101.0)
    assert evaluate(live_value(player, 1)) == pytest.approx(0.5)


def test_an_audio_expression_fades_rather_than_snapping(shader_scene):
    spec = FadeSpec(2.0, "linear", [FadeParam(1, "program", "speed")])
    player = build(shader_scene, fade=spec, uniform_values=("x*2", "0"))
    player.goTo(0)
    player.goTo(1)
    player.tick({}, 100.0)
    player.tick({}, 101.0)

    assert evaluate(live_value(player, 1), x=3.0) == pytest.approx(3.0)


def test_identical_endpoints_are_not_wrapped_in_a_blend(shader_scene):
    """Nothing to ease between, so leave the parameter's own string alone
    rather than replacing it with a no-op blend."""
    spec = FadeSpec(2.0, "linear", [FadeParam(1, "program", "speed")])
    player = build(shader_scene, fade=spec, uniform_values=("0.5", "0.5"))
    player.goTo(0)
    player.goTo(1)

    assert live_value(player, 1) == "0.5"
    assert player._active_fade is None


def test_a_fade_pointing_at_a_missing_node_hard_cuts(shader_scene):
    """validate_session reports this; the runtime must not raise into the
    60 Hz audio slot over it."""
    spec = FadeSpec(2.0, "linear", [FadeParam(999, "program", "speed")])
    player = build(shader_scene, fade=spec)
    player.goTo(0)
    player.goTo(1)

    assert live_value(player, 1) == "1"
    assert player._active_fade is None


# -- interruption ---------------------------------------------------------


def test_interrupting_a_fade_resumes_from_the_live_value(shader_scene):
    """Pressing Next mid-fade must not pop. The half-blended expression on
    the parameter becomes the next fade's starting point, so the value at
    the moment of the switch is continuous."""
    spec_b = FadeSpec(2.0, "linear", [FadeParam(1, "program", "speed")])
    spec_c = FadeSpec(2.0, "linear", [FadeParam(1, "program", "speed")])
    session = LiveSession(
        states=[
            SessionState(
                "a", {"type": "manual"}, make_scene([node(1, {"speed": "0"})])
            ),
            SessionState(
                "b",
                {"type": "manual"},
                make_scene([node(1, {"speed": "1"})]),
                fade=spec_b,
            ),
            SessionState(
                "c",
                {"type": "manual"},
                make_scene([node(1, {"speed": "10"})]),
                fade=spec_c,
            ),
        ]
    )
    player = SessionPlayer(shader_scene)
    player.load(session, OPCODES, FEATURES)

    player.goTo(0)
    player.goTo(1)
    player.tick({}, 100.0)
    player.tick({}, 101.0)
    before = evaluate(live_value(player, 1))
    assert before == pytest.approx(0.5)

    player.goTo(2)
    assert evaluate(live_value(player, 1)) == pytest.approx(before)
    assert player._active_fade.entries[0].depth == 1

    player.tick({}, 101.0)
    player.tick({}, 103.0)
    assert live_value(player, 1) == "10"


def test_nesting_stops_at_the_cap(shader_scene):
    """Mashing Next would otherwise grow the expression without bound. Past
    the cap the interrupted fade's clean target becomes the new start --
    one visible step, instead of an unbounded string."""
    spec = FadeSpec(2.0, "linear", [FadeParam(1, "program", "speed")])
    states = [
        SessionState("a", {"type": "manual"}, make_scene([node(1, {"speed": "0"})]))
    ]
    for i in range(1, MAX_NESTING + 3):
        states.append(
            SessionState(
                "s%d" % i,
                {"type": "manual"},
                make_scene([node(1, {"speed": str(i)})]),
                fade=FadeSpec(spec.duration, spec.curve, list(spec.params)),
            )
        )
    player = SessionPlayer(shader_scene)
    player.load(
        session=LiveSession(states=states),
        known_opcodes=OPCODES,
        known_features=FEATURES,
    )

    player.goTo(0)
    depths = []
    now = 100.0
    for index in range(1, len(states)):
        player.goTo(index)
        depths.append(player._active_fade.entries[0].depth)
        player.tick({}, now)
        now += 0.1
        player.tick({}, now)

    assert max(depths) <= MAX_NESTING
    assert 0 in depths[1:], "the cap must reset the nesting, not stall at it"
    assert len(live_value(player, 1)) < 2000


# -- serialization safety -------------------------------------------------


def test_finishFade_leaves_a_clean_target_string(faded):
    """Capture and Overwrite serialize the live scene. A blend expression
    reaching the file would be indistinguishable from one the user typed."""
    faded.goTo(1)
    assert "(1-" in live_value(faded, 1)

    faded.finishFade()

    assert live_value(faded, 1) == "1"
    assert faded._active_fade is None


def test_finishFade_is_safe_with_no_fade_running(faded):
    faded.finishFade()
    faded.finishFade()


def test_loading_a_new_session_drops_a_running_fade(faded, shader_scene):
    faded.goTo(1)
    assert faded._active_fade is not None

    faded.load(LiveSession(states=[]), OPCODES, FEATURES)
    assert faded._active_fade is None


def test_a_failed_switch_starts_no_fade(shader_scene):
    """goTo is all-or-nothing: a staging failure rolls the scene back, and a
    fade left running against it would drive parameters on a state the
    session is not showing."""
    spec = FadeSpec(2.0, "linear", [FadeParam(1, "program", "speed")])
    session = LiveSession(
        states=[
            SessionState(
                "a", {"type": "manual"}, make_scene([node(1, {"speed": "0"})])
            ),
            SessionState(
                "b",
                {"type": "manual"},
                make_scene(
                    [node(1, {"speed": "1"})],
                    [{"id": 5, "start": 999, "end": 998, "edge_type": 2}],
                ),
                fade=spec,
            ),
        ]
    )
    player = SessionPlayer(shader_scene)
    player.load(session, OPCODES, FEATURES)
    player.goTo(0)

    assert player.goTo(1) is False
    assert player._active_fade is None
    assert live_value(player, 1) == "0"
