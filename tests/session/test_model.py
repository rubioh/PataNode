import json
import os

import pytest

from session.model import (
    SESSION_VERSION,
    InvalidSessionFile,
    LiveSession,
    SessionState,
    UnknownSessionVersion,
)


def make_scene(node_ids, edges=None):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": [
            {
                "id": nid,
                "title": "N%d" % nid,
                "pos_x": 0,
                "pos_y": 0,
                "inputs": [],
                "outputs": [],
                "content": {},
            }
            for nid in node_ids
        ],
        "edges": edges or [],
    }


def make_session():
    return LiveSession(
        name="set",
        states=[
            SessionState("intro", {"type": "manual"}, make_scene([1, 2])),
            SessionState("build", {"type": "manual"}, make_scene([1, 2, 3])),
        ],
    )


def test_round_trip_preserves_states():
    session = make_session()
    restored = LiveSession.from_dict(session.to_dict())

    assert restored.name == "set"
    assert [s.name for s in restored.states] == ["intro", "build"]
    assert restored.states[1].scene["nodes"][2]["id"] == 3


def test_to_dict_writes_current_version():
    assert make_session().to_dict()["version"] == SESSION_VERSION


def test_unknown_version_is_rejected():
    data = make_session().to_dict()
    data["version"] = 99
    with pytest.raises(UnknownSessionVersion):
        LiveSession.from_dict(data)


def test_missing_version_is_rejected():
    data = make_session().to_dict()
    del data["version"]
    with pytest.raises(UnknownSessionVersion):
        LiveSession.from_dict(data)


def test_load_rejects_malformed_json(tmp_path):
    path = tmp_path / "broken.pnlive"
    path.write_text('{"version": 1, "states": [')
    with pytest.raises(InvalidSessionFile):
        LiveSession.load(str(path))


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "set.pnlive"
    make_session().save(str(path))

    restored = LiveSession.load(str(path))
    assert [s.name for s in restored.states] == ["intro", "build"]


def test_failed_save_leaves_existing_file_intact(tmp_path, monkeypatch):
    path = tmp_path / "set.pnlive"
    original = "PRECIOUS"
    path.write_text(original)

    session = make_session()
    monkeypatch.setattr(
        session, "to_dict", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    with pytest.raises(RuntimeError):
        session.save(str(path))

    assert path.read_text() == original
    assert not (tmp_path / "set.pnlive.tmp").exists()


def test_failed_write_leaves_existing_file_intact(tmp_path, monkeypatch):
    """Verify atomic save cleanup runs when os.replace fails after tmp file exists."""
    path = tmp_path / "set.pnlive"
    original = "PRECIOUS"
    path.write_text(original)

    real_replace = os.replace

    def failing_replace(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError):
        make_session().save(str(path))

    monkeypatch.setattr(os, "replace", real_replace)
    assert path.read_text() == original
    assert not (tmp_path / "set.pnlive.tmp").exists()


def test_compute_union_yields_one_node_per_id():
    union = make_session().compute_union()
    assert sorted(n["id"] for n in union) == [1, 2, 3]


def test_capture_appends_after_current():
    session = make_session()
    index = session.capture(make_scene([1, 2, 3, 4]), "drop", after_index=0)

    assert index == 1
    assert [s.name for s in session.states] == ["intro", "drop", "build"]


def test_capture_with_no_index_appends_at_end():
    session = make_session()
    index = session.capture(make_scene([9]), "outro")

    assert index == 2
    assert session.states[2].name == "outro"


def test_overwrite_replaces_scene_but_keeps_name_and_trigger():
    session = make_session()
    session.states[0].trigger = {"type": "audio", "feature": "kick_count", "count": 4}
    session.overwrite(0, make_scene([7]))

    assert session.states[0].name == "intro"
    assert session.states[0].trigger["count"] == 4
    assert session.states[0].scene["nodes"][0]["id"] == 7


def test_delete_and_move_reorder_states():
    session = make_session()
    session.capture(make_scene([5]), "outro")

    session.move(0, 2)
    assert [s.name for s in session.states] == ["build", "outro", "intro"]

    session.delete(1)
    assert [s.name for s in session.states] == ["build", "intro"]


def test_rename():
    session = make_session()
    session.rename(1, "drop")
    assert session.states[1].name == "drop"


def test_saved_file_is_valid_json_with_states(tmp_path):
    path = tmp_path / "set.pnlive"
    make_session().save(str(path))

    data = json.loads(path.read_text())
    assert data["version"] == SESSION_VERSION
    assert len(data["states"]) == 2


def test_loop_defaults_off():
    assert make_session().loop is False


def test_loop_key_is_omitted_when_off():
    """A session that never used looping round-trips byte-identically, the
    same reason `fade` is omitted -- see the SESSION_VERSION comment."""
    assert "loop" not in make_session().to_dict()


def test_loop_round_trips_when_on():
    session = make_session()
    session.loop = True

    data = session.to_dict()
    assert data["loop"] is True
    assert LiveSession.from_dict(data).loop is True


def test_loop_defaults_off_for_a_file_written_before_the_feature():
    data = make_session().to_dict()
    data.pop("loop", None)
    assert LiveSession.from_dict(data).loop is False
