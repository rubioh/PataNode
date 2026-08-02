from session.model import LiveSession, SessionState
from session.propagation import (
    diff_scene_params,
    diff_scene_structure,
    propagate_params,
    propagate_structure,
)


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


def edge(eid, start, end):
    return {"id": eid, "start": start, "end": end, "edge_type": 2}


def node_with_sockets(nid, input_ids=None, output_ids=None, cpu=None, gpu=None):
    """Create a node with specified socket ids for inputs and outputs."""
    if input_ids is None:
        input_ids = []
    if output_ids is None:
        output_ids = []

    data = {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": 100,
        "inputs": [{"id": sid, "index": i} for i, sid in enumerate(input_ids)],
        "outputs": [{"id": sid, "index": i} for i, sid in enumerate(output_ids)],
        "content": {},
    }
    if cpu is not None:
        data["cpu_adaptable_parameters"] = cpu
    if gpu is not None:
        data["gpu_adaptable_parameters"] = gpu
    return data


def test_structural_diff_detects_added_and_removed_nodes():
    baseline = make_scene([node(1), node(2)])
    current = make_scene([node(1), node(3)])

    diff = diff_scene_structure(baseline, current)

    assert [n["id"] for n in diff.added_nodes] == [3]
    assert diff.removed_node_ids == {2}


def test_structural_diff_detects_added_and_removed_edges():
    baseline = {**make_scene([node(1)]), "edges": [edge(10, 1, 2)]}
    current = {**make_scene([node(1)]), "edges": [edge(11, 2, 3)]}

    diff = diff_scene_structure(baseline, current)

    assert [e["id"] for e in diff.added_edges] == [11]
    assert diff.removed_edge_ids == {10}


def test_propagate_structure_adds_node_to_later_states():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1), node(3)])),
            SessionState("b", {}, make_scene([node(1)])),
        ]
    )
    diff = diff_scene_structure(make_scene([node(1)]), make_scene([node(1), node(3)]))

    outcome = propagate_structure(session, 0, diff)

    assert [n["id"] for n in session.states[1].scene["nodes"]] == [1, 3]
    assert len(outcome.applied) == 1


def test_propagate_structure_removes_node_from_later_states():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1)])),
            SessionState("b", {}, make_scene([node(1), node(2)])),
        ]
    )
    diff = diff_scene_structure(make_scene([node(1), node(2)]), make_scene([node(1)]))

    propagate_structure(session, 0, diff)

    assert [n["id"] for n in session.states[1].scene["nodes"]] == [1]


def test_propagate_structure_does_not_duplicate_existing_nodes():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1), node(3)])),
            SessionState("b", {}, make_scene([node(1), node(3)])),
        ]
    )
    diff = diff_scene_structure(make_scene([node(1)]), make_scene([node(1), node(3)]))

    propagate_structure(session, 0, diff)

    assert [n["id"] for n in session.states[1].scene["nodes"]] == [1, 3]


def test_propagate_structure_preview_does_not_mutate():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1), node(3)])),
            SessionState("b", {}, make_scene([node(1)])),
        ]
    )
    diff = diff_scene_structure(make_scene([node(1)]), make_scene([node(1), node(3)]))

    propagate_structure(session, 0, diff, apply=False)

    assert [n["id"] for n in session.states[1].scene["nodes"]] == [1]


def test_propagate_structure_skips_removal_if_state_added_wiring():
    """If a later state wired a NEW edge into the removed node, keep it and skip."""
    session = LiveSession(
        states=[
            # State 0: nodes 1 and 2, edge from 1 to 2
            SessionState(
                "a",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100]),
                            node_with_sockets(2, input_ids=[200]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200)],
                },
            ),
            # State 1: inherited nodes 1 and 2, inherited edge 10
            SessionState(
                "b",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100]),
                            node_with_sockets(2, input_ids=[200]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200)],
                },
            ),
            # State 2: inherited nodes 1 and 2, inherited edge 10, PLUS new edge to node 2
            SessionState(
                "c",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100]),
                            node_with_sockets(2, input_ids=[200, 201]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200), edge(11, 100, 201)],
                },
            ),
        ]
    )

    # Remove node 1 from state 0 (which had edge 10: 100->200)
    diff = diff_scene_structure(
        {
            **make_scene(
                [
                    node_with_sockets(1, output_ids=[100]),
                    node_with_sockets(2, input_ids=[200]),
                ]
            ),
            "edges": [edge(10, 100, 200)],
        },
        {
            **make_scene([node_with_sockets(2, input_ids=[200])]),
            "edges": [edge(10, 100, 200)],  # Edge 10 removed, but node 1 had it
        },
    )

    outcome = propagate_structure(session, 0, diff)

    # State 1 should lose node 1 (inherited untouched)
    assert [n["id"] for n in session.states[1].scene["nodes"]] == [2]
    assert len([a for a in outcome.applied if a[0] == 1]) == 1

    # State 2 should keep node 1 (added new edge to node 2)
    assert [n["id"] for n in session.states[2].scene["nodes"]] == [1, 2]
    assert len([s for s in outcome.skipped if s[0] == 2]) == 1


def test_propagate_structure_removes_inherited_node():
    """If a later state merely inherited the node, it should still be removed."""
    session = LiveSession(
        states=[
            # State 0: nodes 1 and 2, edge between them
            SessionState(
                "a",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100]),
                            node_with_sockets(2, input_ids=[200]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200)],
                },
            ),
            # State 1: inherited nodes 1 and 2, inherited edge
            SessionState(
                "b",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100]),
                            node_with_sockets(2, input_ids=[200]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200)],
                },
            ),
        ]
    )

    # Remove node 1 from state 0
    diff = diff_scene_structure(
        {
            **make_scene(
                [
                    node_with_sockets(1, output_ids=[100]),
                    node_with_sockets(2, input_ids=[200]),
                ]
            ),
            "edges": [edge(10, 100, 200)],
        },
        {
            **make_scene([node_with_sockets(2, input_ids=[200])]),
            "edges": [],
        },
    )

    outcome = propagate_structure(session, 0, diff)

    # State 1 should lose node 1
    assert [n["id"] for n in session.states[1].scene["nodes"]] == [2]
    assert len(outcome.applied) == 2  # node 1 removal and edge 10 removal
    assert len(outcome.skipped) == 0


def test_propagate_structure_skipped_removal_in_preview():
    """Preview mode should report the same skips without mutating."""
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100]),
                            node_with_sockets(2, input_ids=[200]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200)],
                },
            ),
            SessionState(
                "b",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100]),
                            node_with_sockets(2, input_ids=[200, 201]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200), edge(11, 100, 201)],
                },
            ),
        ]
    )

    diff = diff_scene_structure(
        {
            **make_scene(
                [
                    node_with_sockets(1, output_ids=[100]),
                    node_with_sockets(2, input_ids=[200]),
                ]
            ),
            "edges": [edge(10, 100, 200)],
        },
        {
            **make_scene([node_with_sockets(2, input_ids=[200])]),
            "edges": [],
        },
    )

    outcome = propagate_structure(session, 0, diff, apply=False)

    # State 1 should keep node 1 (had new wiring)
    assert [n["id"] for n in session.states[1].scene["nodes"]] == [1, 2]
    assert len(outcome.skipped) == 1
    assert outcome.skipped[0][0] == 1  # state_index


def test_propagate_structure_skips_edge_removal_if_state_rewired():
    """If a later state rewired an edge (changed endpoints), keep it and skip."""
    session = LiveSession(
        states=[
            # State 0: edge 10 connects socket 100->200
            SessionState(
                "a",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100, 101]),
                            node_with_sockets(2, input_ids=[200, 201]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200)],
                },
            ),
            # State 1: inherited edge 10 as-is
            SessionState(
                "b",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100, 101]),
                            node_with_sockets(2, input_ids=[200, 201]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200)],
                },
            ),
            # State 2: rewired edge 10 to use different sockets (101->201)
            SessionState(
                "c",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100, 101]),
                            node_with_sockets(2, input_ids=[200, 201]),
                        ]
                    ),
                    "edges": [edge(10, 101, 201)],  # Different from baseline
                },
            ),
        ]
    )

    # Remove edge 10 from state 0 (which had it as 100->200)
    diff = diff_scene_structure(
        {
            **make_scene(
                [
                    node_with_sockets(1, output_ids=[100, 101]),
                    node_with_sockets(2, input_ids=[200, 201]),
                ]
            ),
            "edges": [edge(10, 100, 200)],
        },
        {
            **make_scene(
                [
                    node_with_sockets(1, output_ids=[100, 101]),
                    node_with_sockets(2, input_ids=[200, 201]),
                ]
            ),
            "edges": [],
        },
    )

    outcome = propagate_structure(session, 0, diff)

    # State 1 should lose edge 10 (inherited unchanged)
    assert [e["id"] for e in session.states[1].scene["edges"]] == []
    assert len([a for a in outcome.applied if "edge 10" in str(a)]) == 1

    # State 2 should keep edge 10 (rewired it)
    assert len(session.states[2].scene["edges"]) == 1
    assert session.states[2].scene["edges"][0]["id"] == 10
    assert session.states[2].scene["edges"][0]["start"] == 101  # Rewired
    assert len([s for s in outcome.skipped if s[0] == 2]) == 1


def test_propagate_structure_removes_unchanged_edge():
    """If a later state has an unchanged edge, it should still be removed."""
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100]),
                            node_with_sockets(2, input_ids=[200]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200)],
                },
            ),
            SessionState(
                "b",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100]),
                            node_with_sockets(2, input_ids=[200]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200)],  # Identical to baseline
                },
            ),
        ]
    )

    diff = diff_scene_structure(
        {
            **make_scene(
                [
                    node_with_sockets(1, output_ids=[100]),
                    node_with_sockets(2, input_ids=[200]),
                ]
            ),
            "edges": [edge(10, 100, 200)],
        },
        {
            **make_scene(
                [
                    node_with_sockets(1, output_ids=[100]),
                    node_with_sockets(2, input_ids=[200]),
                ]
            ),
            "edges": [],
        },
    )

    outcome = propagate_structure(session, 0, diff)

    # State 1 should lose edge 10
    assert [e["id"] for e in session.states[1].scene["edges"]] == []
    assert len(outcome.applied) == 1
    assert len(outcome.skipped) == 0


def test_propagate_structure_skipped_edge_removal_in_preview():
    """Preview mode should report edge rewiring skip without mutating."""
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100, 101]),
                            node_with_sockets(2, input_ids=[200, 201]),
                        ]
                    ),
                    "edges": [edge(10, 100, 200)],
                },
            ),
            SessionState(
                "b",
                {},
                {
                    **make_scene(
                        [
                            node_with_sockets(1, output_ids=[100, 101]),
                            node_with_sockets(2, input_ids=[200, 201]),
                        ]
                    ),
                    "edges": [edge(10, 101, 201)],  # Rewired
                },
            ),
        ]
    )

    diff = diff_scene_structure(
        {
            **make_scene(
                [
                    node_with_sockets(1, output_ids=[100, 101]),
                    node_with_sockets(2, input_ids=[200, 201]),
                ]
            ),
            "edges": [edge(10, 100, 200)],
        },
        {
            **make_scene(
                [
                    node_with_sockets(1, output_ids=[100, 101]),
                    node_with_sockets(2, input_ids=[200, 201]),
                ]
            ),
            "edges": [],
        },
    )

    outcome = propagate_structure(session, 0, diff, apply=False)

    # State 1 should keep edge 10 (rewired)
    assert len(session.states[1].scene["edges"]) == 1
    assert session.states[1].scene["edges"][0]["id"] == 10
    assert len(outcome.skipped) == 1
    assert outcome.skipped[0][0] == 1  # state_index
