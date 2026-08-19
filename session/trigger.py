"""Trigger evaluation for live sessions.

Pure functions: no Qt, no GL, no scene. A trigger decides when playback
advances from one state to the next.

`evaluate_trigger` returns a possibly-updated entry snapshot. Callers must
store it back — that is how hold-timing and counter-reset recovery stay
free of hidden state.
"""

from typing import NamedTuple

# The only monotonic counters the audio engine exposes
# (audio/audio_event.py:50-58). The on_tempo* family looks similar but is
# phase data, not counters (audio/audio_bpm.py:40-53).
COUNTER_FEATURES = ("kick_count", "hat_count", "snare_count")


class TriggerResult(NamedTuple):
    should_advance: bool
    entry: dict


def make_entry_snapshot(trigger: dict, features: dict, now: float) -> dict:
    """Capture whatever state this trigger needs to measure from."""
    if trigger.get("type") == "time":
        # Anchored on arrival: `now` is time.monotonic() (app.py), already
        # large when the app has been up a while, so a timer must measure
        # elapsed-since-entry rather than compare `now` against `seconds`.
        return {"entered_at": now}

    if trigger.get("type") != "audio":
        return {}

    if "count" in trigger:
        return {"count_at_entry": features.get(trigger.get("feature"), 0)}

    if "above" in trigger:
        return {"above_since": None}

    return {}


def evaluate_trigger(
    trigger: dict, features: dict, entry: dict, now: float
) -> TriggerResult:
    """Decide whether playback should advance."""
    if trigger.get("type") == "time":
        # trigger["seconds"] unguarded on purpose: a timer with no duration
        # is a malformed trigger, and SessionPlayer.tick's KeyError guard
        # turns it into "never advances" plus one status warning. Defaulting
        # to some number here would instead invent a tempo the set never
        # asked for. validate_session rejects the shape at load time.
        return TriggerResult(
            now - entry.get("entered_at", now) >= trigger["seconds"], entry
        )

    if trigger.get("type") != "audio":
        return TriggerResult(False, entry)

    value = features.get(trigger.get("feature"))
    if value is None:
        return TriggerResult(False, entry)

    if "count" in trigger:
        delta = value - entry.get("count_at_entry", 0)
        if delta < 0:
            # Audio engine restarted and the counter went back to zero.
            # Re-snapshot rather than advancing or hanging forever.
            return TriggerResult(False, {"count_at_entry": value})
        return TriggerResult(delta >= trigger["count"], entry)

    if "above" in trigger:
        if value > trigger["above"]:
            since = entry.get("above_since")
            if since is None:
                return TriggerResult(False, {"above_since": now})
            return TriggerResult(now - since >= trigger["hold"], entry)
        return TriggerResult(False, {"above_since": None})

    return TriggerResult(False, entry)
