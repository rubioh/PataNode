from session.model import LiveSession, SessionState
from session.propagation import diff_scene_params, propagate_params


def node(nid, cpu=None, gpu=None):
    data = {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": 100,
        "inputs": [],
        "outputs": [],
        "content": {},
    }
    if cpu is not None:
        data["cpu_adaptable_parameters"] = cpu
    if gpu is not None:
        data["gpu_adaptable_parameters"] = gpu
    return data


def params(**uniforms):
    return {
        "program": {
            name: {"eval_function": {"value": value}}
            for name, value in uniforms.items()
        }
    }


def make_scene(nodes):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes),
        "edges": [],
    }


def test_diff_finds_changed_cpu_parameter():
    baseline = make_scene([node(1, cpu=params(radius="0.35"))])
    current = make_scene([node(1, cpu=params(radius="0.8"))])

    changes = diff_scene_params(baseline, current)

    assert len(changes) == 1
    assert changes[0].node_id == 1
    assert changes[0].kind == "cpu"
    assert changes[0].uniform == "radius"
    assert changes[0].old_value == "0.35"
    assert changes[0].new_value == "0.8"


def test_diff_finds_changed_gpu_parameter():
    baseline = make_scene([node(1, gpu=params(speed="x"))])
    current = make_scene([node(1, gpu=params(speed="x/3"))])

    changes = diff_scene_params(baseline, current)

    assert len(changes) == 1
    assert changes[0].kind == "gpu"
    assert changes[0].new_value == "x/3"


def test_diff_ignores_unchanged_parameters():
    baseline = make_scene([node(1, cpu=params(radius="0.35"))])
    current = make_scene([node(1, cpu=params(radius="0.35"))])

    assert diff_scene_params(baseline, current) == []


def test_propagation_applies_where_value_still_matches():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1, cpu=params(radius="0.8"))])),
            SessionState("b", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
            SessionState("c", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
        ]
    )
    changes = [
        c
        for c in diff_scene_params(
            make_scene([node(1, cpu=params(radius="0.35"))]),
            make_scene([node(1, cpu=params(radius="0.8"))]),
        )
    ]

    outcome = propagate_params(session, 0, changes)

    assert len(outcome.applied) == 2
    assert outcome.skipped == []
    for state in session.states[1:]:
        value = state.scene["nodes"][0]["cpu_adaptable_parameters"]["program"][
            "radius"
        ]["eval_function"]["value"]
        assert value == "0.8"


def test_propagation_skips_states_that_diverged():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1, cpu=params(radius="0.8"))])),
            SessionState("b", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
            SessionState("c", {}, make_scene([node(1, cpu=params(radius="0.9"))])),
        ]
    )
    changes = diff_scene_params(
        make_scene([node(1, cpu=params(radius="0.35"))]),
        make_scene([node(1, cpu=params(radius="0.8"))]),
    )

    outcome = propagate_params(session, 0, changes)

    assert len(outcome.applied) == 1
    assert len(outcome.skipped) == 1

    state_index, change, actual = outcome.skipped[0]
    assert state_index == 2
    assert change.uniform == "radius"
    assert actual == "0.9"

    # The diverged state keeps its own value
    assert (
        session.states[2].scene["nodes"][0]["cpu_adaptable_parameters"]["program"][
            "radius"
        ]["eval_function"]["value"]
        == "0.9"
    )


def test_preview_does_not_mutate_the_session():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1, cpu=params(radius="0.8"))])),
            SessionState("b", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
        ]
    )
    changes = diff_scene_params(
        make_scene([node(1, cpu=params(radius="0.35"))]),
        make_scene([node(1, cpu=params(radius="0.8"))]),
    )

    outcome = propagate_params(session, 0, changes, apply=False)

    assert len(outcome.applied) == 1
    assert (
        session.states[1].scene["nodes"][0]["cpu_adaptable_parameters"]["program"][
            "radius"
        ]["eval_function"]["value"]
        == "0.35"
    )


def test_propagation_never_touches_earlier_states():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
            SessionState("b", {}, make_scene([node(1, cpu=params(radius="0.8"))])),
            SessionState("c", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
        ]
    )
    changes = diff_scene_params(
        make_scene([node(1, cpu=params(radius="0.35"))]),
        make_scene([node(1, cpu=params(radius="0.8"))]),
    )

    propagate_params(session, 1, changes)

    assert (
        session.states[0].scene["nodes"][0]["cpu_adaptable_parameters"]["program"][
            "radius"
        ]["eval_function"]["value"]
        == "0.35"
    )


def test_propagation_ignores_states_missing_the_node():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1, cpu=params(radius="0.8"))])),
            SessionState("b", {}, make_scene([node(2)])),
        ]
    )
    changes = diff_scene_params(
        make_scene([node(1, cpu=params(radius="0.35"))]),
        make_scene([node(1, cpu=params(radius="0.8"))]),
    )

    outcome = propagate_params(session, 0, changes)

    assert outcome.applied == []
    assert outcome.skipped == []
