import pytest

from session.trigger import (
    COUNTER_FEATURES,
    evaluate_trigger,
    make_entry_snapshot,
)


def test_manual_trigger_never_advances():
    trigger = {"type": "manual"}
    entry = make_entry_snapshot(trigger, {"kick_count": 5}, 0.0)
    result = evaluate_trigger(trigger, {"kick_count": 500}, entry, 100.0)
    assert result.should_advance is False


def test_counter_advances_after_n_events():
    trigger = {"type": "audio", "feature": "kick_count", "count": 8}
    entry = make_entry_snapshot(trigger, {"kick_count": 100}, 0.0)

    result = evaluate_trigger(trigger, {"kick_count": 107}, entry, 1.0)
    assert result.should_advance is False

    result = evaluate_trigger(trigger, {"kick_count": 108}, entry, 2.0)
    assert result.should_advance is True


def test_counter_reset_re_snapshots_instead_of_advancing():
    """Audio engine restart drops kick_count to 0; delta goes negative."""
    trigger = {"type": "audio", "feature": "kick_count", "count": 8}
    entry = make_entry_snapshot(trigger, {"kick_count": 100}, 0.0)

    result = evaluate_trigger(trigger, {"kick_count": 2}, entry, 5.0)
    assert result.should_advance is False
    assert result.entry["count_at_entry"] == 2

    result = evaluate_trigger(trigger, {"kick_count": 10}, result.entry, 6.0)
    assert result.should_advance is True


def test_threshold_requires_sustained_hold():
    trigger = {"type": "audio", "feature": "low_slow", "above": 0.7, "hold": 2.0}
    entry = make_entry_snapshot(trigger, {"low_slow": 0.1}, 0.0)

    entry = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 10.0).entry
    result = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 11.5)
    assert result.should_advance is False

    result = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 12.0)
    assert result.should_advance is True


def test_threshold_resets_when_signal_drops():
    trigger = {"type": "audio", "feature": "low_slow", "above": 0.7, "hold": 2.0}
    entry = make_entry_snapshot(trigger, {"low_slow": 0.1}, 0.0)

    entry = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 10.0).entry
    entry = evaluate_trigger(trigger, {"low_slow": 0.2}, entry, 11.0).entry
    assert entry["above_since"] is None

    entry = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 11.5).entry
    result = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 12.6)
    assert result.should_advance is False


def test_missing_feature_never_advances():
    trigger = {"type": "audio", "feature": "nonexistent", "count": 1}
    entry = make_entry_snapshot(trigger, {}, 0.0)
    result = evaluate_trigger(trigger, {}, entry, 10.0)
    assert result.should_advance is False


def test_counter_features_are_the_three_real_counters():
    assert COUNTER_FEATURES == ("kick_count", "hat_count", "snare_count")


def test_time_trigger_advances_once_the_duration_has_elapsed():
    trigger = {"type": "time", "seconds": 8.0}
    entry = make_entry_snapshot(trigger, {}, 100.0)

    result = evaluate_trigger(trigger, {}, entry, 107.9)
    assert result.should_advance is False

    result = evaluate_trigger(trigger, {}, entry, 108.0)
    assert result.should_advance is True


def test_time_trigger_measures_from_entry_not_from_zero():
    """The app has been up for a while, so `now` is a large monotonic
    value. Without anchoring on entry, `now >= seconds` would be true on
    the very first tick and every timed state would flip instantly."""
    trigger = {"type": "time", "seconds": 8.0}
    entry = make_entry_snapshot(trigger, {}, 5000.0)

    assert evaluate_trigger(trigger, {}, entry, 5001.0).should_advance is False


def test_time_trigger_ignores_audio_features():
    trigger = {"type": "time", "seconds": 8.0}
    entry = make_entry_snapshot(trigger, {"kick_count": 5}, 0.0)

    assert (
        evaluate_trigger(trigger, {"kick_count": 9999}, entry, 1.0).should_advance
        is False
    )


def test_time_trigger_missing_seconds_raises_for_the_tick_guard():
    """SessionPlayer.tick catches KeyError and degrades to 'never
    advances' with one status warning -- same contract as a threshold
    trigger missing 'hold'."""
    trigger = {"type": "time"}
    entry = make_entry_snapshot(trigger, {}, 0.0)

    with pytest.raises(KeyError):
        evaluate_trigger(trigger, {}, entry, 100.0)
