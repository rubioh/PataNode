import copy

import pytest

from session.model import LiveSession, SessionState
from session.player import SessionPlayer


def node(nid, op_code=100, inputs=(), outputs=()):
    return {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": op_code,
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
    }


def make_scene(nodes, edges=()):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes),
        "edges": list(edges),
    }


OPCODES = {100}
FEATURES = {"kick_count"}


@pytest.fixture
def loaded(scene):
    """Two states: state 0 has no edges, state 1 wires node 1 -> node 2."""
    n1 = node(1, outputs=[10])
    n2 = node(2, inputs=[20])
    session = LiveSession(
        states=[
            SessionState("a", {"type": "manual"}, make_scene([n1, n2])),
            SessionState(
                "b",
                {"type": "manual"},
                make_scene(
                    [n1, n2], [{"id": 5, "start": 10, "end": 20, "edge_type": 2}]
                ),
            ),
        ]
    )
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)
    return player


def test_goto_wires_the_states_edges(loaded):
    assert loaded.goTo(1) is True

    assert len(loaded.scene.edges) == 1
    assert loaded.scene.edges[0].start_socket.id == 10
    assert loaded.scene.edges[0].end_socket.id == 20


def test_goto_back_removes_edges(loaded):
    loaded.goTo(1)
    loaded.goTo(0)

    assert loaded.scene.edges == []


def test_goto_never_destroys_union_nodes(loaded):
    loaded.goTo(0)
    assert len(loaded.scene.nodes) == 2

    loaded.goTo(1)
    assert len(loaded.scene.nodes) == 2


def test_goto_is_idempotent(loaded):
    loaded.goTo(1)
    loaded.goTo(1)

    assert len(loaded.scene.edges) == 1


def test_goto_updates_current_index(loaded):
    loaded.goTo(1)
    assert loaded.current_index == 1


def test_next_and_prev_walk_the_session(loaded):
    loaded.goTo(0)

    assert loaded.next() is True
    assert loaded.current_index == 1

    assert loaded.prev() is True
    assert loaded.current_index == 0


def test_next_at_end_does_not_advance(loaded):
    loaded.goTo(1)
    assert loaded.next() is False
    assert loaded.current_index == 1


def test_prev_at_start_does_not_move(loaded):
    loaded.goTo(0)
    assert loaded.prev() is False
    assert loaded.current_index == 0


def test_failed_transition_leaves_scene_on_current_state(loaded):
    loaded.goTo(1)

    # Corrupt the target state so building it raises
    loaded.session.states[0].scene["edges"] = [
        {"id": 7, "start": 999, "end": 998, "edge_type": 2}
    ]

    assert loaded.goTo(0) is False
    assert loaded.current_index == 1
    assert len(loaded.scene.edges) == 1


def test_goto_does_not_mutate_the_stored_session(scene):
    """Node.deserialize sorts data['inputs'] in place -- deepcopy guards it.

    Two input sockets with descending index values, so an in-place sort has
    something real to reorder (a single-socket list is a sort no-op and
    would prove nothing regardless of the deepcopy). The "before" snapshot
    is a deep copy too: a shallow dict copy shares the inputs list object
    and would still compare equal to itself after an in-place sort.
    """
    n1 = node(1, outputs=[10])
    n2 = node(2, inputs=[21, 20])
    n2["inputs"][0]["index"] = 1
    n2["inputs"][1]["index"] = 0
    state_scene = make_scene(
        [n1, n2], [{"id": 5, "start": 10, "end": 20, "edge_type": 2}]
    )
    session = LiveSession(states=[SessionState("a", {"type": "manual"}, state_scene)])
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)

    before = copy.deepcopy(session.states[0].scene["nodes"])
    player.goTo(0)
    assert session.states[0].scene["nodes"] == before


def test_goto_pulls_exactly_one_render(scene):
    """The transition must re-render, and must not cascade doing it."""
    calls = []
    n1 = node(1, outputs=[10])
    n2 = node(2, inputs=[20])
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                make_scene(
                    [n1, n2], [{"id": 5, "start": 10, "end": 20, "edge_type": 2}]
                ),
            )
        ]
    )
    player = SessionPlayer(scene, on_evaluate=lambda: calls.append(1))
    player.load(session, OPCODES, FEATURES)

    assert player.goTo(0) is True
    assert len(calls) == 1


def test_failed_goto_does_not_pull_a_render(scene):
    calls = []
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                make_scene(
                    [node(1)], [{"id": 7, "start": 999, "end": 998, "edge_type": 2}]
                ),
            )
        ]
    )
    player = SessionPlayer(scene, on_evaluate=lambda: calls.append(1))
    player.load(session, OPCODES, FEATURES)

    assert player.goTo(0) is False
    assert calls == []


def test_goto_reports_failure_through_status_callback(scene):
    messages = []
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                make_scene(
                    [node(1)], [{"id": 7, "start": 999, "end": 998, "edge_type": 2}]
                ),
            )
        ]
    )
    player = SessionPlayer(scene, on_status=messages.append)
    player.load(session, OPCODES, FEATURES)

    assert player.goTo(0) is False
    assert messages


def test_goto_rolls_back_when_apply_parameters_raises(loaded):
    """Guards the gap ShaderNode.deserialize can hit: an unguarded key
    access after super().deserialize() (node/shader_node_base.py) can raise
    past Node.deserialize's own try/except. _stage_edges can't catch this --
    it only validates edges -- so goTo must roll back anything
    _apply_parameters/_rewire already did.

    The fixture's plain Node can't reach that code path (it never raises),
    so the failure is injected directly: monkeypatch one live node's
    deserialize to blow up on the target state's (malformed) data, the same
    shape of failure ShaderNode can hit for real. It only raises once --
    like the real bug, the failure is triggered by the *target* state's bad
    data, not by the valid data the rollback restores -- so the rollback
    call must be able to actually repair the node, not just avoid a second
    crash. If this test is satisfied by a fixture that can never fail on its
    own, it isn't testing the rollback -- it has to force the failure.
    """
    loaded.goTo(1)

    live_node_2 = next(n for n in loaded.scene.nodes if n.id == 2)
    original_deserialize = live_node_2.deserialize
    call_count = {"n": 0}

    def flaky_deserialize(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated ShaderNode.deserialize failure")
        return original_deserialize(*args, **kwargs)

    live_node_2.deserialize = flaky_deserialize

    messages = []
    loaded.on_status = messages.append
    evaluated = []
    loaded.on_evaluate = lambda: evaluated.append(1)

    assert loaded.goTo(0) is False

    # current_index must not advance and on_evaluate must not fire
    assert loaded.current_index == 1
    assert evaluated == []

    # the scene must still show state 1's edges, untouched
    assert len(loaded.scene.edges) == 1
    assert loaded.scene.edges[0].start_socket.id == 10
    assert loaded.scene.edges[0].end_socket.id == 20

    assert messages
