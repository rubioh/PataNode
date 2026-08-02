"""Regression tests for the three work-losing save/load defects.

C1 - saveToFile truncated the target before it knew serialize() would succeed
C2 - InputAudioNode's op_code came from hash(), randomized per process
C3 - a failed load reported success, so a later save overwrote the good file
"""

import json

import pytest

from nodeeditor.node_scene import InvalidFile, Scene

# --------------------------------------------------------------------------
# C1: saving must never destroy the previous file
# --------------------------------------------------------------------------


def test_failed_serialize_leaves_existing_file_intact(two_node_scene, tmp_path):
    target = tmp_path / "scene.json"
    original = json.dumps({"nodes": ["precious"], "edges": []}, indent=4)
    target.write_text(original)

    def boom():
        raise RuntimeError("serialize blew up")

    two_node_scene.serialize = boom

    with pytest.raises(RuntimeError):
        two_node_scene.saveToFile(str(target))

    assert target.read_text() == original, "existing scene was clobbered"
    assert not (tmp_path / "scene.json.tmp").exists(), "temp file left behind"


def test_failed_write_leaves_existing_file_intact(
    two_node_scene, tmp_path, monkeypatch
):
    target = tmp_path / "scene.json"
    original = json.dumps({"nodes": ["precious"], "edges": []}, indent=4)
    target.write_text(original)

    real_open = open

    def failing_open(path, *args, **kwargs):
        if str(path).endswith(".tmp"):
            raise OSError(28, "No space left on device")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)

    with pytest.raises(OSError):
        two_node_scene.saveToFile(str(target))

    monkeypatch.undo()
    assert target.read_text() == original


def test_scene_not_marked_clean_when_save_fails(two_node_scene, tmp_path):
    target = tmp_path / "scene.json"
    target.write_text("{}")

    two_node_scene.has_been_modified = True

    def boom():
        raise RuntimeError("nope")

    two_node_scene.serialize = boom

    with pytest.raises(RuntimeError):
        two_node_scene.saveToFile(str(target))

    assert (
        two_node_scene.has_been_modified
    ), "scene was marked saved even though the save failed"


def test_save_load_round_trip(two_node_scene, tmp_path, qapp):
    target = tmp_path / "scene.json"
    two_node_scene.saveToFile(str(target))

    assert target.stat().st_size > 0
    json.loads(target.read_text())  # valid JSON

    reloaded = Scene()
    reloaded.loadFromFile(str(target))

    assert len(reloaded.nodes) == 2
    assert len(reloaded.edges) == 1
    assert sorted(n.title for n in reloaded.nodes) == ["Node A", "Node B"]

    edge = reloaded.edges[0]
    assert edge.start_socket is not None
    assert edge.end_socket is not None
    assert edge.start_socket.node.title == "Node A"
    assert edge.end_socket.node.title == "Node B"

    assert not reloaded.deserialization_errors
    assert not reloaded.has_been_modified


# --------------------------------------------------------------------------
# C2: op_codes are written into scene files, so they must be stable
# --------------------------------------------------------------------------


def test_audio_input_opcode_is_deterministic():
    import program.program_conf  # noqa: F401  (breaks the import cycle)
    from audio.transforms.utils.input_audio_features import OP_CODE_INPUTAF

    # sum(ord(c) for c in "input_af") -- pinned so a regression to hash(),
    # which is randomized per process, fails here instead of quietly making
    # every saved scene containing this node unloadable.
    assert OP_CODE_INPUTAF == 854


def test_audio_input_opcode_resolves_back_to_its_class():
    import program.program_conf  # noqa: F401
    from audio.transforms.utils.input_audio_features import (
        OP_CODE_INPUTAF,
        InputAudioNode,
    )
    from node.node_conf import get_class_from_opcode

    assert get_class_from_opcode(OP_CODE_INPUTAF) is InputAudioNode


# --------------------------------------------------------------------------
# C3: a broken load must not pass as a clean one
# --------------------------------------------------------------------------


def test_truncated_json_raises_invalid_file(scene, tmp_path):
    target = tmp_path / "truncated.json"
    target.write_text('{"nodes": [')

    with pytest.raises(InvalidFile):
        scene.loadFromFile(str(target))


def test_empty_file_raises_invalid_file(scene, tmp_path):
    """saved/fx3.json is 0 bytes on disk -- the C1 bug's calling card."""
    target = tmp_path / "empty.json"
    target.write_text("")

    with pytest.raises(InvalidFile):
        scene.loadFromFile(str(target))


def test_missing_nodes_key_raises(scene, tmp_path):
    target = tmp_path / "no_nodes.json"
    target.write_text(json.dumps({"id": 1, "scene_width": 100, "scene_height": 100}))

    with pytest.raises(KeyError):
        scene.loadFromFile(str(target))


def test_failed_load_does_not_claim_the_filename(scene, tmp_path):
    """Otherwise Ctrl+S writes the half-loaded scene over the good file."""
    target = tmp_path / "no_nodes.json"
    target.write_text(json.dumps({"id": 1, "scene_width": 100, "scene_height": 100}))

    with pytest.raises(Exception):
        scene.loadFromFile(str(target))

    assert scene.filename != str(target)


def test_edge_referencing_missing_node_is_reported(two_node_scene, tmp_path, qapp):
    data = two_node_scene.serialize()

    # Drop the second node but keep the edge pointing at it -- this is what an
    # unregistered op_code or a failed node deserialize produces.
    data["nodes"] = data["nodes"][:1]

    target = tmp_path / "dangling.json"
    target.write_text(json.dumps(data, indent=4))

    reloaded = Scene()
    reloaded.loadFromFile(str(target))

    assert (
        reloaded.deserialization_errors
    ), "dangling edge was dropped silently -- the user would never know"
    assert len(reloaded.edges) == 0, "a dangling edge survived into the scene"


def test_unknown_node_class_is_reported_not_swallowed(scene, tmp_path):
    def always_fails(data):
        raise ValueError("OpCode 999999 is not registered")

    scene.setNodeClassSelector(always_fails)

    data = {
        "id": 1,
        "scene_width": 100,
        "scene_height": 100,
        "nodes": [
            {
                "id": 2,
                "title": "Ghost",
                "pos_x": 0,
                "pos_y": 0,
                "inputs": [],
                "outputs": [],
                "content": {},
            }
        ],
        "edges": [],
    }
    target = tmp_path / "ghost.json"
    target.write_text(json.dumps(data))

    scene.loadFromFile(str(target))

    assert scene.deserialization_errors
    assert any("Ghost" in err for err in scene.deserialization_errors)
