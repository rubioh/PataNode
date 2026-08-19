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


def test_malformed_trigger_degrades_instead_of_crashing_tick(scene):
    """IMPORTANT: session/validation.py should reject a threshold trigger
    missing 'hold' at load time, but tick() must not trust that as its only
    line of defense -- a hand-edited session file could still carry one
    past load. trigger.py:evaluate_trigger does trigger["hold"]
    unconditionally once "above" is present; unguarded, that KeyError would
    propagate out of tick() into app.py's on_audio_job_finished, a Qt slot
    called 60 times a second mid-performance.

    A trigger missing 'hold' bypasses validate_session's check by being
    constructed directly on the SessionState, simulating a file saved by an
    older build or hand-edited around the validator.
    """
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "kick_count", "above": 0.5},
                make_scene([node(1)]),
            ),
            SessionState("b", {"type": "manual"}, make_scene([node(1), node(2)])),
        ]
    )
    built = SessionPlayer(scene)
    built.load(session, {100}, {"kick_count"})
    built.goTo(0)
    built.play()

    messages = []
    built.on_status = messages.append

    # Tick 1: anchors the entry snapshot (make_entry_snapshot only sets
    # above_since=None for this shape -- no "hold" access yet).
    built.tick({"kick_count": 0.1}, 1.0)
    assert built.current_index == 0

    # Tick 2: value crosses "above" for the first time. evaluate_trigger
    # sets above_since=now and returns early -- still no "hold" access.
    built.tick({"kick_count": 0.9}, 2.0)
    assert built.current_index == 0

    # Tick 3: value is still above threshold, so above_since is no longer
    # None -- evaluate_trigger now does `now - since >= trigger["hold"]`,
    # which raises KeyError without the guard. It must not escape tick(),
    # and the state must never auto-advance.
    built.tick({"kick_count": 0.9}, 3.0)
    assert built.current_index == 0
    assert messages


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


def test_playback_wraps_to_the_first_state_when_looping(scene):
    """The looping counterpart of test_playback_stops_at_the_last_state:
    the last state's own trigger fires and playback rolls back to state 0.
    """
    session = LiveSession(
        states=[
            SessionState("a", {"type": "manual"}, make_scene([node(1)])),
            SessionState(
                "b",
                {"type": "audio", "feature": "kick_count", "count": 4},
                make_scene([node(1), node(2)]),
            ),
        ],
        loop=True,
    )
    built = SessionPlayer(scene)
    built.load(session, {100}, {"kick_count"})
    built.goTo(1)
    built.play()

    built.tick({"kick_count": 10}, 1.0)  # anchors the baseline
    assert built.current_index == 1

    built.tick({"kick_count": 14}, 2.0)  # delta 4 -> fires, wrapping
    assert built.current_index == 0


def timed_player(scene, seconds=8.0, loop=False):
    session = LiveSession(
        states=[
            SessionState(
                "a", {"type": "time", "seconds": seconds}, make_scene([node(1)])
            ),
            SessionState(
                "b",
                {"type": "time", "seconds": seconds},
                make_scene([node(1), node(2)]),
            ),
        ],
        loop=loop,
    )
    built = SessionPlayer(scene)
    built.load(session, {100}, set())
    built.goTo(0)
    return built


def test_timed_states_advance_on_their_own(scene):
    player = timed_player(scene, seconds=8.0)
    player.play()

    player.tick({}, 1000.0)  # anchors the timer
    assert player.current_index == 0

    player.tick({}, 1007.9)
    assert player.current_index == 0

    player.tick({}, 1008.0)
    assert player.current_index == 1


def test_a_timed_loop_runs_scene_to_scene_without_stopping(scene):
    player = timed_player(scene, seconds=5.0, loop=True)
    player.play()

    now = 1000.0
    seen = []
    for _ in range(120):  # two minutes of ticks at 0.5 s
        player.tick({}, now)
        seen.append(player.current_index)
        now += 0.5

    assert seen[-1] in (0, 1)
    # 60 s of playback at 5 s per state: the set must have cycled several
    # times, which only happens if the last state wraps back to the first.
    assert seen.count(0) > 1 and seen.count(1) > 1
    assert any(seen[i] == 1 and seen[i + 1] == 0 for i in range(len(seen) - 1))


def test_pausing_restarts_the_timer_instead_of_banking_the_pause(scene):
    """Pause for a minute on an 8 s scene and hit Play: without re-anchoring
    on resume, the first tick sees a 60 s elapsed time and flips the state
    instantly, mid-note.
    """
    player = timed_player(scene, seconds=8.0)
    player.play()
    player.tick({}, 1000.0)  # anchors at 1000

    player.pause()
    player.play()

    player.tick({}, 1060.0)  # 60 s later: re-anchors, does not advance
    assert player.current_index == 0

    player.tick({}, 1065.0)  # only 5 s since the resume
    assert player.current_index == 0

    player.tick({}, 1068.0)  # a full 8 s since the resume
    assert player.current_index == 1
