from session.fade import FadeParam, FadeSpec
from session.model import LiveSession, SessionState
from session.validation import validate_session


def node(nid, op_code=100, inputs=(), outputs=()):
    return {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": op_code,
        "inputs": [{"id": sid, "index": i} for i, sid in enumerate(inputs)],
        "outputs": [{"id": sid, "index": i} for i, sid in enumerate(outputs)],
        "content": {},
    }


def scene(nodes, edges=()):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes),
        "edges": list(edges),
    }


OPCODES = {100, 200}
FEATURES = {"kick_count", "low_slow", "on_tempo8"}


def test_clean_session_produces_no_findings():
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                scene(
                    [node(1, outputs=[10]), node(2, inputs=[20])],
                    [{"id": 5, "start": 10, "end": 20, "edge_type": 2}],
                ),
            )
        ]
    )
    assert validate_session(session, OPCODES, FEATURES) == []


def test_unregistered_opcode_is_reported():
    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, scene([node(1, op_code=999)]))]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 1
    assert findings[0].category == "node"
    assert findings[0].state_index == 0
    assert "999" in findings[0].message


def test_edge_referencing_missing_socket_is_reported():
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                scene(
                    [node(1, outputs=[10])],
                    [{"id": 5, "start": 10, "end": 99, "edge_type": 2}],
                ),
            )
        ]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 1
    assert findings[0].category == "edge"


def test_trigger_with_unknown_feature_is_reported():
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "nope", "above": 0.5, "hold": 1.0},
                scene([node(1)]),
            )
        ]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 1
    assert findings[0].category == "trigger"


def test_counter_trigger_on_non_counter_feature_is_reported():
    """on_tempo8 is a phase value, not a counter -- unusable for count triggers."""
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "on_tempo8", "count": 8},
                scene([node(1)]),
            )
        ]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 1
    assert findings[0].category == "trigger"
    assert "counter" in findings[0].message.lower()


def test_counter_trigger_on_real_counter_is_accepted():
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "kick_count", "count": 8},
                scene([node(1)]),
            )
        ]
    )
    assert validate_session(session, OPCODES, FEATURES) == []


def test_threshold_trigger_missing_hold_is_reported():
    """trigger.py:62 does trigger["hold"] unconditionally once "above" is
    present -- a KeyError straight into the 60 Hz audio timer if this ever
    reaches SessionPlayer.tick unguarded.
    """
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "kick_count", "above": 0.5},
                scene([node(1)]),
            )
        ]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 1
    assert findings[0].category == "trigger"
    assert "hold" in findings[0].message


def test_audio_trigger_with_neither_count_nor_above_is_reported():
    """Without count or above, evaluate_trigger's fallthrough always
    returns should_advance=False -- the state would silently never advance,
    stranding the performer mid-set with no diagnostic.
    """
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "kick_count"},
                scene([node(1)]),
            )
        ]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 1
    assert findings[0].category == "trigger"


def test_threshold_trigger_with_above_and_hold_is_accepted():
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "kick_count", "above": 0.5, "hold": 1.0},
                scene([node(1)]),
            )
        ]
    )
    assert validate_session(session, OPCODES, FEATURES) == []


def test_all_findings_reported_together_with_state_indices():
    session = LiveSession(
        states=[
            SessionState("a", {"type": "manual"}, scene([node(1, op_code=999)])),
            SessionState(
                "b",
                {"type": "audio", "feature": "nope", "count": 2},
                scene([node(2, op_code=888)]),
            ),
        ]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 3
    assert {f.state_index for f in findings} == {0, 1}


# -- fades ----------------------------------------------------------------


def faded_node(nid, uniforms):
    data = node(nid)
    data["gpu_adaptable_parameters"] = {
        "program": {
            name: {"eval_function": {"value": value}}
            for name, value in uniforms.items()
        }
    }
    return data


def faded_session(fade, uniforms={"speed": "1"}):
    return LiveSession(
        states=[
            SessionState(
                "a", {"type": "manual"}, scene([faded_node(1, uniforms)]), fade=fade
            )
        ]
    )


def test_a_valid_fade_produces_no_findings():
    session = faded_session(
        FadeSpec(2.0, "smoothstep", [FadeParam(1, "program", "speed")])
    )
    assert validate_session(session, OPCODES, FEATURES) == []


def test_a_fade_targeting_a_missing_node_is_reported():
    """SessionPlayer skips what it cannot resolve rather than raising into
    the 60 Hz audio slot, so without this the transition would just look
    like it forgot to fade."""
    session = faded_session(
        FadeSpec(2.0, "linear", [FadeParam(999, "program", "speed")])
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert [f.category for f in findings] == ["fade"]
    assert "999" in findings[0].message


def test_a_fade_targeting_an_undeclared_uniform_is_reported():
    session = faded_session(FadeSpec(2.0, "linear", [FadeParam(1, "program", "nope")]))
    findings = validate_session(session, OPCODES, FEATURES)

    assert [f.category for f in findings] == ["fade"]
    assert "nope" in findings[0].message


def test_a_non_positive_duration_is_reported():
    """Duration 0 makes every fade land on its target on the first tick --
    a hard cut wearing a fade's clothes."""
    session = faded_session(FadeSpec(0.0, "linear", [FadeParam(1, "program", "speed")]))
    findings = validate_session(session, OPCODES, FEATURES)

    assert [f.category for f in findings] == ["fade"]
    assert "positive" in findings[0].message


def test_an_unknown_curve_is_reported():
    session = faded_session(FadeSpec(2.0, "bouncy", [FadeParam(1, "program", "speed")]))
    findings = validate_session(session, OPCODES, FEATURES)

    assert [f.category for f in findings] == ["fade"]
    assert "bouncy" in findings[0].message


def test_a_state_without_a_fade_is_never_flagged():
    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, scene([faded_node(1, {})]))]
    )
    assert validate_session(session, OPCODES, FEATURES) == []
