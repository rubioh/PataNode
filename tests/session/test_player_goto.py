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


def test_rewire_does_not_fire_onInputChanged(loaded):
    """CRITICAL: evaluation must be suppressed during the rewire.

    Edge.remove() without silent=True notifies both endpoint nodes
    (nodeeditor/node_edge.py:290-303) -- onEdgeConnectionChanged, and
    onInputChanged on the input-socket side. For a real ShaderNode,
    onInputChanged calls self.eval() (node/shader_node_base.py:400-406): a
    full upstream render pull. Firing this per removed edge while the graph
    is half torn down cascades N evaluations into a single transition,
    exactly the mid-set hitch the union model exists to prevent. Plain
    nodeeditor.Node.onInputChanged only marks dirty and never evaluates, so
    a naive test using the un-suppressed call count on plain Node would
    still pass -- the count itself, not its side effect, is what must be
    zero.
    """
    loaded.goTo(1)  # wires edge 10->20; nothing to remove yet, so no calls

    calls = {"n": 0}
    for live_node in loaded.scene.nodes:
        original = live_node.onInputChanged

        def counting_onInputChanged(socket=None, _orig=original):
            calls["n"] += 1
            return _orig(socket)

        live_node.onInputChanged = counting_onInputChanged

    assert loaded.goTo(0) is True  # removes the edge wired above

    assert calls["n"] == 0


def test_goto_wires_the_states_edges(loaded):
    assert loaded.goTo(1) is True

    assert len(loaded.scene.edges) == 1
    assert loaded.scene.edges[0].start_socket.id == 10
    assert loaded.scene.edges[0].end_socket.id == 20


def test_goto_back_removes_edges(loaded):
    loaded.goTo(1)
    loaded.goTo(0)

    assert loaded.scene.edges == []


def test_goto_never_destroys_union_nodes(scene):
    """The union invariant: a node absent from state i's node list is not
    destroyed by goTo(i) -- it just sits disconnected, keeping its current
    parameters, until some later state wires it back in.

    State 0 mentions only node 1; node 2 is only in state 1. If goTo(0)
    behaved like Scene.deserialize's normal reuse-and-remove semantics (or
    any destroy-and-rebuild implementation of _apply_parameters), node 2
    would be deleted on goTo(0) and rebuilt from scratch on goTo(1), losing
    whatever live parameter values it held. A fixture where every state
    lists every node (as the `loaded` fixture above does) cannot catch
    this -- a destroy-and-rebuild implementation passes it identically.
    """
    n1 = node(1, outputs=[10])
    n2 = node(2, inputs=[20])
    n2["title"] = "N2-live"
    n2["pos_x"] = 42

    session = LiveSession(
        states=[
            SessionState("a", {"type": "manual"}, make_scene([n1])),
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

    live_node_2 = next(n for n in player.scene.nodes if n.id == 2)
    live_node_2.title = "N2-mutated-in-editor"
    live_node_2.setPos(999, 999)

    assert player.goTo(0) is True
    # node 2 is absent from state 0's node list, but the union model must
    # not destroy it -- just leave it disconnected with its own values.
    assert len(player.scene.nodes) == 2
    still_alive = next(n for n in player.scene.nodes if n.id == 2)
    assert still_alive.title == "N2-mutated-in-editor"
    assert still_alive.pos.x() == 999

    assert player.goTo(1) is True
    assert len(player.scene.nodes) == 2


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


def test_goto_reverts_node_parameters_when_apply_parameters_raises(scene):
    """Guards the gap ShaderNode.deserialize can hit: an unguarded key
    access after super().deserialize() (node/shader_node_base.py) can raise
    past Node.deserialize's own try/except. _stage_edges can't catch this --
    it only validates edges -- so goTo must roll back anything
    _apply_parameters already did.

    The fixture's plain Node can't reach that code path (it never raises),
    so the failure is injected directly: monkeypatch one live node's
    deserialize to blow up on the target state's data, the same shape of
    failure ShaderNode can hit for real.

    States 0 and 1 give node 1 a different title/pos_x, and node 1 is
    ordered before node 2 in each state's node list, so by the time node 2's
    (injected) failure fires, node 1 has already been mutated to state 1's
    values. Asserting node 1 is back to state *0*'s values -- not merely
    that some rollback ran -- is the point: a rollback call that is a no-op
    (e.g. patched to `pass`) leaves node 1 on state 1's values and this
    assertion is what catches that, not the edge count.
    """
    n1_state0 = node(1, outputs=[10])
    n1_state0["title"] = "N1-a"
    n1_state0["pos_x"] = 0

    n1_state1 = node(1, outputs=[10])
    n1_state1["title"] = "N1-b"
    n1_state1["pos_x"] = 100

    n2 = node(2, inputs=[20])

    session = LiveSession(
        states=[
            SessionState("a", {"type": "manual"}, make_scene([n1_state0, n2])),
            SessionState("b", {"type": "manual"}, make_scene([n1_state1, n2])),
        ]
    )
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)

    assert player.goTo(0) is True

    live_node_2 = next(n for n in player.scene.nodes if n.id == 2)
    original_deserialize = live_node_2.deserialize
    call_count = {"n": 0}

    def flaky_deserialize(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated ShaderNode.deserialize failure")
        return original_deserialize(*args, **kwargs)

    live_node_2.deserialize = flaky_deserialize

    messages = []
    player.on_status = messages.append
    evaluated = []
    player.on_evaluate = lambda: evaluated.append(1)

    assert player.goTo(1) is False

    # current_index must not advance and on_evaluate must not fire
    assert player.current_index == 0
    assert evaluated == []

    # node 1 must be back on state 0's values, not left on state 1's
    live_node_1 = next(n for n in player.scene.nodes if n.id == 1)
    assert live_node_1.title == "N1-a"
    assert live_node_1.pos.x() == 0

    assert messages


def test_goto_restores_edges_when_rewire_raises(loaded, monkeypatch):
    """Guards the other half of the rollback: _rewire removes every current
    edge *before* constructing the replacements, so a failure partway
    through edge construction leaves the scene with zero edges unless the
    rollback restores them.

    _apply_parameters must succeed here so the failure is isolated to
    _rewire -- the previous test already covers a failure during parameter
    application. The construction failure is injected by patching the
    `Edge` name `session.player` imports (not `nodeeditor.node_edge.Edge`
    itself), so the rollback path -- which goes through
    `Scene.deserialize`, using its own direct import of the real `Edge` --
    is unaffected and can actually recreate the removed edge. It raises
    only on the first call (the real transition's attempt); the rollback's
    own edge construction is expected to succeed.
    """
    assert loaded.goTo(1) is True

    import session.player as player_module

    real_edge_cls = player_module.Edge
    call_count = {"n": 0}

    def flaky_edge(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated edge construction failure")
        return real_edge_cls(*args, **kwargs)

    monkeypatch.setattr(player_module, "Edge", flaky_edge)

    messages = []
    loaded.on_status = messages.append
    evaluated = []
    loaded.on_evaluate = lambda: evaluated.append(1)

    # Re-apply state 1: _stage_edges and _apply_parameters succeed, then
    # _rewire tears down the existing edge and fails constructing its
    # replacement.
    assert loaded.goTo(1) is False

    assert loaded.current_index == 1
    assert evaluated == []

    # the edge must be back, not merely "still there" -- _rewire already
    # removed it before the injected failure fired.
    assert len(loaded.scene.edges) == 1
    assert loaded.scene.edges[0].start_socket.id == 10
    assert loaded.scene.edges[0].end_socket.id == 20

    assert messages


def test_next_wraps_to_the_first_state_when_looping(loaded):
    loaded.session.loop = True
    loaded.goTo(1)

    assert loaded.next() is True
    assert loaded.current_index == 0


def test_prev_wraps_to_the_last_state_when_looping(loaded):
    loaded.session.loop = True
    loaded.goTo(0)

    assert loaded.prev() is True
    assert loaded.current_index == 1


def test_looping_next_before_the_first_goto_still_starts_at_state_zero(loaded):
    """load() leaves current_index at -1. Wrapping must not turn that into
    a jump to the last state -- the first Next still opens the set."""
    loaded.session.loop = True
    assert loaded.current_index == -1

    assert loaded.next() is True
    assert loaded.current_index == 0


def test_looping_next_on_a_single_state_session_re_enters_it(scene):
    session = LiveSession(
        states=[SessionState("only", {"type": "manual"}, make_scene([node(1)]))],
        loop=True,
    )
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)
    player.goTo(0)

    assert player.next() is True
    assert player.current_index == 0


def test_looping_next_on_an_empty_session_does_nothing(scene):
    player = SessionPlayer(scene)
    player.load(LiveSession(loop=True), OPCODES, FEATURES)

    assert player.next() is False
    assert player.prev() is False
    assert player.current_index == -1
