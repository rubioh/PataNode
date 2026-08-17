"""The render loop paces itself on absolute deadlines.

`_scheduleNextFrame` advances a deadline by exactly one period per frame,
regardless of how long the frame took, and asks the timer for whatever is
left. The naive alternative -- sleep the period *after* each frame -- gives a
period of `period + frame duration`, which measured 29 ms and 34 fps against a
16.67 ms target. The absolute deadline also absorbs Qt's whole-millisecond
timer resolution: a 16.67 ms period alternates between 16 and 17 ms sleeps and
averages out correctly.

Driven against a stub rather than a real widget: the method touches only
_frame_period_ns, _next_deadline_ns and _frame_timer, so a real GL context and
a real QTimer are not needed to test the arithmetic, which is the part with
edge cases.
"""

import pytest

from gui.widgets import shader_widget
from gui.widgets.shader_widget import ShaderWidget

MS = 1_000_000
NS_PER_S = 1_000_000_000


class FakeTimer:
    """Stands in for the single-shot QTimer."""

    def __init__(self):
        self.delays = []
        self.active = False

    def start(self, delay_ms):
        self.delays.append(delay_ms)
        self.active = True

    def stop(self):
        self.active = False

    def isActive(self):
        return self.active


class FakeClock:
    def __init__(self, now_ns=0):
        self.now_ns = now_ns

    def perf_counter_ns(self):
        return self.now_ns

    def advance_ms(self, ms):
        self.now_ns += int(ms * MS)


class Loop:
    """A ShaderWidget reduced to what the scheduler actually touches."""

    def __init__(self, fps):
        self._frame_period_ns = int(NS_PER_S / fps) if fps else 0
        self._next_deadline_ns = 0
        self._frame_timer = FakeTimer()

    # Bound under their real names: ensureRenderLoopRunning calls
    # self._scheduleNextFrame, so an alias alone would not be enough.
    _scheduleNextFrame = ShaderWidget._scheduleNextFrame
    ensureRenderLoopRunning = ShaderWidget.ensureRenderLoopRunning

    schedule = _scheduleNextFrame
    ensure = ensureRenderLoopRunning


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(shader_widget, "time", fake)
    return fake


def run(loop, clock, frame_ms, frames):
    """Render `frames` frames each costing `frame_ms`, return the delays asked."""
    for _ in range(frames):
        clock.advance_ms(frame_ms)
        loop.schedule()
        # The timer then waits the delay it was given before the next frame.
        clock.advance_ms(loop._frame_timer.delays[-1])

    return loop._frame_timer.delays


def achieved_fps(loop, clock, frame_ms, frames=120):
    start = clock.now_ns
    run(loop, clock, frame_ms, frames)
    elapsed_s = (clock.now_ns - start) / NS_PER_S

    return frames / elapsed_s


@pytest.mark.parametrize(
    "target, frame_ms, expected_fps",
    [
        # Comfortably inside the budget: the target is held exactly.
        (60, 0.5, 60),
        (60, 5, 60),
        (60, 13, 60),
        # Over budget. The rate falls to an exact fraction of the target
        # rather than drifting to a ragged in-between value -- for motion, a
        # steady 30 beats an irregular 26.
        (60, 20, 30),
        (60, 40, 20),
        # A different target paces just as exactly.
        (30, 5, 30),
        (72, 5, 72),
    ],
)
def test_it_holds_the_target_or_an_exact_fraction_of_it(
    clock, target, frame_ms, expected_fps
):
    loop = Loop(target)

    assert achieved_fps(loop, clock, frame_ms) == pytest.approx(expected_fps, rel=0.02)


def test_the_deadline_advances_by_one_period_per_frame(clock):
    loop = Loop(60)
    period = loop._frame_period_ns

    loop.schedule()
    first = loop._next_deadline_ns

    clock.advance_ms(5)
    loop.schedule()

    # Exactly one period on, not "one period from now" -- that difference is
    # what stops the 5 ms of frame time from being added to the interval.
    assert loop._next_deadline_ns - first == period


def test_whole_millisecond_rounding_averages_out(clock):
    # A 16.67 ms period cannot be expressed in the whole milliseconds Qt
    # timers take. The deadline is what keeps the average honest.
    loop = Loop(60)
    delays = run(loop, clock, frame_ms=0, frames=60)

    assert set(delays) <= {16, 17}
    assert sum(delays) / len(delays) == pytest.approx(16.67, abs=0.1)


def test_an_overrun_never_fires_a_backlog_back_to_back(clock):
    loop = Loop(60)
    # One frame that blows four periods of budget.
    clock.advance_ms(70)
    loop.schedule()

    # The skipped slots are dropped, not queued: the next deadline is in the
    # future, so the delay asked for is positive.
    assert loop._frame_timer.delays[-1] > 0
    assert loop._next_deadline_ns > clock.now_ns


def test_uncapped_never_asks_for_a_qt_zero_timer(clock):
    # A zero-delay QTimer is not an OS timer: the dispatcher posts itself an
    # event and so never blocks, spinning through every pending event between
    # frames. Uncapped must still yield.
    loop = Loop(0)
    loop.schedule()

    assert loop._frame_timer.delays == [1]


def test_restarting_drops_a_stale_deadline(clock):
    loop = Loop(60)
    loop.schedule()

    # The window is hidden for a while, so the loop stops and the deadline
    # goes stale.
    loop._frame_timer.stop()
    clock.advance_ms(5000)
    loop.ensure()

    # Resuming must begin the cadence from now, not try to catch up on the
    # five seconds of slots it missed.
    assert loop._frame_timer.delays[-1] == pytest.approx(17, abs=1)


def test_ensure_leaves_an_already_running_loop_alone(clock):
    loop = Loop(60)
    loop.schedule()
    before = list(loop._frame_timer.delays)

    # The watchdog fires while the loop is turning. It must be idempotent, or
    # it would double the frame rate.
    loop.ensure()
    loop.ensure()

    assert loop._frame_timer.delays == before
