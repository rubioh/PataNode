"""The pure fade model: easing, expression blending, candidate discovery."""

import json

import pytest

from session.fade import (
    CURVES,
    DEFAULT_CURVE,
    FadeParam,
    FadeSpec,
    blend_expression,
    ease,
    fade_candidates,
    is_blendable,
)
from session.model import LiveSession, SessionState


def evaluate(expression, x):
    """Exactly what ProgramBase.getAdaptableEvaluationForUniform does.

    Reproduced rather than imported because importing program_base pulls in
    moderngl and the whole node registry. If that method's semantics ever
    change, this helper is the thing that has to change with it.
    """
    try:
        return float(eval(expression))
    except Exception:
        return x


# -- easing ---------------------------------------------------------------


@pytest.mark.parametrize("curve", ["linear", "smoothstep"])
def test_every_curve_pins_both_endpoints(curve):
    """A curve that does not reach 1 would leave the parameter short of its
    target forever, since the fade's final write is the only thing that
    corrects it."""
    assert ease(0.0, curve) == 0.0
    assert ease(1.0, curve) == 1.0


@pytest.mark.parametrize("curve", ["linear", "smoothstep"])
def test_easing_is_monotonic_and_clamped(curve):
    values = [ease(i / 20.0, curve) for i in range(21)]
    assert values == sorted(values)
    assert ease(-5.0, curve) == 0.0
    assert ease(5.0, curve) == 1.0


def test_unknown_curve_degrades_to_linear():
    """A hand-edited session file must not crash the 60 Hz audio tick.
    validate_session reports the bad curve; the runtime still has to run."""
    assert ease(0.5, "does-not-exist") == 0.5


# -- blend expressions ----------------------------------------------------


def test_blend_reads_as_each_endpoint_at_the_extremes():
    expression = blend_expression(".2", ".9", 0.0)
    assert evaluate(expression, x=7.0) == pytest.approx(0.2)

    expression = blend_expression(".2", ".9", 1.0)
    assert evaluate(expression, x=7.0) == pytest.approx(0.9)


def test_blend_is_linear_in_between():
    expression = blend_expression(".2", ".9", 0.5)
    assert evaluate(expression, x=7.0) == pytest.approx(0.55)


def test_an_audio_driven_expression_fades_like_a_literal():
    """The point of blending strings rather than numbers: "x*2" is a live
    audio-bound value, and it has to ease just as well as ".9"."""
    expression = blend_expression("x*2", ".9", 0.25)
    assert evaluate(expression, x=3.0) == pytest.approx(0.75 * 6.0 + 0.25 * 0.9)


def test_a_compound_old_side_is_parenthesised():
    """Without the parentheses, (1-a)*x+2 is a different number from
    (1-a)*(x+2) -- and the bug would be invisible at a=0 and a=1."""
    expression = blend_expression("x+2", "0", 0.5)
    assert evaluate(expression, x=4.0) == pytest.approx(3.0)


def test_a_nested_blend_still_evaluates():
    """An interrupted fade wraps the whole live expression as the new `old`
    side. Four levels deep must still be valid Python."""
    expression = "x*2"
    for a in (0.3, 0.4, 0.5, 0.6):
        expression = blend_expression(expression, ".9", a)
    assert evaluate(expression, x=1.0) != 1.0  # not the raw-x fallback


def test_blendable_rejects_what_would_build_a_syntax_error():
    assert is_blendable(".9")
    assert is_blendable("x*2")
    assert not is_blendable("")
    assert not is_blendable("   ")
    assert not is_blendable(None)
    assert not is_blendable(0.9)


# -- spec serialization ---------------------------------------------------


def test_fade_spec_round_trips():
    spec = FadeSpec(
        duration=2.5,
        curve="linear",
        params=[
            FadeParam(1, "program", "speed"),
            FadeParam(2, "program", "baseBlend", from_value="0", to_value="1"),
        ],
    )
    assert FadeSpec.from_dict(spec.to_dict()) == spec


def test_unset_endpoints_are_omitted_not_nulled():
    """`from`/`to` absent means "resolve at switch time", and a fade block
    full of explicit nulls is harder to hand-edit."""
    data = FadeParam(1, "program", "speed").to_dict()
    assert "from" not in data and "to" not in data
    assert FadeParam.from_dict(data).from_value is None


def test_no_fade_means_no_fade():
    assert FadeSpec.from_dict(None) is None
    assert FadeSpec.from_dict({}) is None


def test_a_session_without_fades_writes_no_fade_key(tmp_path):
    """The version stayed at 1, so every existing .pnlive must round-trip
    unchanged -- a stray "fade": null in every state would not."""
    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, {"nodes": [], "edges": []})]
    )
    path = tmp_path / "s.pnlive"
    session.save(str(path))

    raw = json.loads(path.read_text())
    assert "fade" not in raw["states"][0]
    assert LiveSession.load(str(path)).states[0].fade is None


def test_a_fade_survives_a_save_and_reload(tmp_path):
    spec = FadeSpec(3.0, "linear", [FadeParam(1, "program", "speed", to_value="1")])
    session = LiveSession(
        states=[
            SessionState("a", {"type": "manual"}, {"nodes": [], "edges": []}, fade=spec)
        ]
    )
    path = tmp_path / "s.pnlive"
    session.save(str(path))

    assert LiveSession.load(str(path)).states[0].fade == spec


# -- candidate discovery --------------------------------------------------


def gpu_node(nid, title, uniforms, cpu=None):
    node = {
        "id": nid,
        "title": title,
        "gpu_adaptable_parameters": {
            "program": {
                name: {"eval_function": {"value": value}}
                for name, value in uniforms.items()
            }
        },
    }
    if cpu:
        node["cpu_adaptable_parameters"] = {
            "program": {
                name: {"eval_function": {"value": value}} for name, value in cpu.items()
            }
        }
    return node


def test_candidates_offer_unchanged_params_too():
    """The Blend case: both states store the same baseBlend and only the
    wiring differs, but sweeping it is exactly what makes the transition a
    crossfade. Listing only what differs would hide it."""
    prev = {"nodes": [gpu_node(1, "Blend", {"baseBlend": "0.5", "bias": "x"})]}
    nxt = {"nodes": [gpu_node(1, "Blend", {"baseBlend": "0.5", "bias": "x*2"})]}

    params = {p["uniform"]: p for p in fade_candidates(prev, nxt)[0]["params"]}

    assert params["baseBlend"]["differs"] is False
    assert params["bias"]["differs"] is True
    assert params["bias"]["from"] == "x" and params["bias"]["to"] == "x*2"


def test_candidates_skip_nodes_only_one_side_has():
    prev = {"nodes": [gpu_node(1, "A", {"speed": "1"})]}
    nxt = {
        "nodes": [
            gpu_node(1, "A", {"speed": "2"}),
            gpu_node(2, "B", {"speed": "3"}),
        ]
    }
    assert [c["node_id"] for c in fade_candidates(prev, nxt)] == [1]


def test_candidates_exclude_cpu_parameters():
    """CPU params are read as raw strings with no eval
    (ProgramBase.getSingleCpuParameters), so a blend expression would reach
    the consumer as literal text."""
    prev = {"nodes": [gpu_node(1, "A", {"speed": "1"}, cpu={"label": "hello"})]}
    nxt = {"nodes": [gpu_node(1, "A", {"speed": "2"}, cpu={"label": "world"})]}

    uniforms = [p["uniform"] for p in fade_candidates(prev, nxt)[0]["params"]]
    assert uniforms == ["speed"]


def test_candidates_drop_unblendable_values():
    prev = {"nodes": [gpu_node(1, "A", {"speed": "", "decay": ".9"})]}
    nxt = {"nodes": [gpu_node(1, "A", {"speed": "2", "decay": ".5"})]}

    uniforms = [p["uniform"] for p in fade_candidates(prev, nxt)[0]["params"]]
    assert uniforms == ["decay"]


def test_a_node_with_nothing_blendable_is_not_listed():
    prev = {"nodes": [gpu_node(1, "A", {})]}
    nxt = {"nodes": [gpu_node(1, "A", {})]}
    assert fade_candidates(prev, nxt) == []


def test_the_default_curve_is_one_validate_session_accepts():
    """FadeSpec defaults it, _validate_fade rejects anything not in CURVES --
    a default outside that set would flag every fade the GUI writes."""
    assert DEFAULT_CURVE in CURVES
