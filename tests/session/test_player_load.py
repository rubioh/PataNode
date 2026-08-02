import copy

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


def test_load_instantiates_the_union_once(scene):
    session = LiveSession(
        states=[
            SessionState("a", {"type": "manual"}, make_scene([node(1), node(2)])),
            SessionState(
                "b", {"type": "manual"}, make_scene([node(1), node(2), node(3)])
            ),
        ]
    )
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)

    assert len(scene.nodes) == 3
    assert sorted(n.id for n in scene.nodes) == [1, 2, 3]


def test_load_wires_no_edges(scene):
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                make_scene(
                    [node(1, outputs=[10]), node(2)],
                    [{"id": 5, "start": 10, "end": 10, "edge_type": 2}],
                ),
            )
        ]
    )
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)

    assert scene.edges == []


def test_load_returns_static_findings(scene):
    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, make_scene([node(1, 999)]))]
    )
    player = SessionPlayer(scene)
    findings = player.load(session, OPCODES, FEATURES)

    assert any(f.category == "node" for f in findings)


def test_load_reports_instantiation_failure_as_finding(scene):
    def explode(data):
        raise ValueError("cannot build node")

    scene.setNodeClassSelector(explode)

    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, make_scene([node(1)]))]
    )
    player = SessionPlayer(scene)
    findings = player.load(session, OPCODES, FEATURES)

    assert any(
        f.category == "node" and "cannot build node" in f.message for f in findings
    )


def test_load_does_not_mutate_the_stored_session(scene):
    """Node.deserialize sorts data['inputs'] in place -- deepcopy guards it.

    Two input sockets with descending index values, so an in-place sort has
    something real to reorder (an empty or single-element list is a sort
    no-op and would prove nothing).
    """
    state_scene = make_scene([node(1, inputs=[20, 10])])
    state_scene["nodes"][0]["inputs"][0]["index"] = 1
    state_scene["nodes"][0]["inputs"][1]["index"] = 0
    session = LiveSession(states=[SessionState("a", {"type": "manual"}, state_scene)])
    before = copy.deepcopy(state_scene["nodes"][0])

    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)

    assert state_scene["nodes"][0] == before


def test_current_index_is_minus_one_before_goto(scene):
    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, make_scene([node(1)]))]
    )
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)

    assert player.current_index == -1
