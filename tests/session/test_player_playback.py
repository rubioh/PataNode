import pytest

from session.model import LiveSession, SessionState
from session.player import SessionPlayer


def node(nid):
    return {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": 100,
        "inputs": [],
        "outputs": [],
        "content": {},
    }


def make_scene(nodes):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes),
        "edges": [],
    }


@pytest.fixture
def player(scene):
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "kick_count", "count": 4},
                make_scene([node(1)]),
            ),
            SessionState("b", {"type": "manual"}, make_scene([node(1), node(2)])),
            SessionState("c", {"type": "manual"}, make_scene([node(1)])),
        ]
    )
    built = SessionPlayer(scene)
    built.load(session, {100}, {"kick_count"})
    built.goTo(0)
    return built


def test_tick_does_nothing_while_paused(player):
    player.pause()
    player.tick({"kick_count": 999}, 10.0)
    assert player.current_index == 0


def test_tick_advances_when_counter_trigger_fires(player):
    player.play()

    # First tick since goTo(0) anchors the baseline (lazily, from live
    # features) instead of evaluating -- see
    # test_cold_start_does_not_advance_on_stale_baseline for why.
    player.tick({"kick_count": 2}, 1.0)
    assert player.current_index == 0

    player.tick({"kick_count": 4}, 2.0)
    assert player.current_index == 0

    player.tick({"kick_count": 6}, 3.0)
    assert player.current_index == 1


def test_manual_trigger_never_auto_advances(player):
    player.goTo(1)
    player.play()

    player.tick({"kick_count": 9999}, 50.0)
    assert player.current_index == 1


def test_manual_next_works_while_playing_and_waiting(player):
    player.play()
    assert player.next() is True
    assert player.current_index == 1


def test_entry_snapshot_resets_on_each_state(player):
    player.play()
    player.tick({"kick_count": 4}, 1.0)  # anchors state 0's baseline at 4
    assert player.current_index == 0
    player.tick({"kick_count": 8}, 1.5)  # delta 4 -> fires
    assert player.current_index == 1

    player.goTo(0)
    # If the entry snapshot were not reset by goTo, this tick's delta from
    # the stale baseline (4) would be 8 - 4 = 4, meeting the threshold and
    # firing immediately. A correct reset instead treats this tick as the
    # new anchor, so nothing fires yet.
    player.tick({"kick_count": 8}, 2.0)
    assert player.current_index == 0


def test_playback_stops_at_the_last_state(player):
    player.goTo(2)
    player.play()
    player.tick({"kick_count": 9999}, 99.0)
    assert player.current_index == 2


def test_cold_start_does_not_advance_on_stale_baseline(scene):
    """The real-world scenario: the app has been running, kick_count is
    already high, and the session is loaded/goTo'd for the first time --
    no tick has run yet. count_at_entry must anchor from the first live
    tick's features, not from the SessionPlayer.__init__ default of {}
    (i.e. 0). Anchoring at 0 would make the very next tick's delta
    (live_count - 0) blow past any reasonable threshold and fire an
    unwanted instant auto-advance right after load.
    """
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "kick_count", "count": 8},
                make_scene([node(1)]),
            ),
            SessionState("b", {"type": "manual"}, make_scene([node(1), node(2)])),
        ]
    )
    built = SessionPlayer(scene)
    built.load(session, {100}, {"kick_count"})
    built.goTo(0)
    built.play()

    built.tick({"kick_count": 5000}, 100.0)
    assert built.current_index == 0

    built.tick({"kick_count": 5004}, 101.0)
    assert built.current_index == 0

    built.tick({"kick_count": 5008}, 102.0)
    assert built.current_index == 1
