import threading
import time

import numpy as np
import pytest

import depth.depth_engine as depth_engine
from depth.depth_engine import (
    INITIAL_BACKOFF_S,
    MAX_BACKOFF_S,
    NO_FRAME_ID,
    DepthEngine,
    DepthStatus,
)
from depth.depth_source import DepthSourceError


class FakeSource:
    """A source that yields an ever-changing frame as fast as it is asked."""

    def __init__(self, width=8, height=4, depth_scale=0.5):
        self.width = width
        self.height = height
        self.depth_scale = depth_scale
        self.open_count = 0
        self.close_count = 0
        self._counter = 0

    def open(self):
        self.open_count += 1
        return self.width, self.height, self.depth_scale

    def read(self):
        time.sleep(0.005)
        self._counter += 1
        return np.full((self.height, self.width), self._counter, dtype=np.uint16)

    def close(self):
        self.close_count += 1


class SlowReadSource:
    """A source whose first read() can be held open past the join timeout.

    Used to reproduce a device that is slow to respond to a stop request:
    close() signals stop, but the thread is stuck inside read() and cannot
    notice until something calls release_first_read().
    """

    def __init__(self, depth_scale):
        self.width = 8
        self.height = 4
        self.depth_scale = depth_scale
        self.open_count = 0
        self.close_count = 0
        self._release_first_read = threading.Event()
        self._counter = 0

    def open(self):
        self.open_count += 1
        return self.width, self.height, self.depth_scale

    def read(self):
        self._counter += 1
        if self._counter == 1:
            self._release_first_read.wait()
            return None
        return np.full((self.height, self.width), self._counter, dtype=np.uint16)

    def release_first_read(self):
        self._release_first_read.set()

    def close(self):
        self.close_count += 1


def wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def source():
    return FakeSource()


@pytest.fixture
def engine(source):
    engine = DepthEngine(lambda: source)
    yield engine
    engine.close()


def test_engine_starts_idle_without_touching_the_device(engine, source):
    assert engine.status is DepthStatus.IDLE
    assert source.open_count == 0
    assert engine.get_frame() is None


def test_acquire_starts_capture_and_publishes_frames(engine, source):
    engine.acquire()

    assert wait_until(lambda: engine.get_frame() is not None)
    frame = engine.get_frame()
    assert engine.status is DepthStatus.STREAMING
    assert frame.width == source.width
    assert frame.height == source.height
    assert frame.depth_scale == source.depth_scale
    assert frame.data.shape == (source.height, source.width)


def test_get_frame_returns_none_when_nothing_is_new(engine):
    engine.acquire()
    assert wait_until(lambda: engine.get_frame() is not None)

    frame = engine.get_frame()

    assert engine.get_frame(since=frame.frame_id) is None


def test_slot_is_latest_wins_not_a_queue(engine):
    engine.acquire()
    assert wait_until(lambda: engine.get_frame() is not None)

    first = engine.get_frame()
    time.sleep(0.1)  # several frames are produced and dropped
    later = engine.get_frame(since=first.frame_id)

    # A queue would hand back first.frame_id + 1. A latest-wins slot skips.
    assert later.frame_id > first.frame_id + 1
    assert later.data[0][0] == later.frame_id


def test_second_acquire_does_not_open_a_second_device(engine, source):
    engine.acquire()
    assert wait_until(lambda: source.open_count == 1)

    engine.acquire()
    time.sleep(0.05)

    assert source.open_count == 1


def test_release_above_zero_keeps_streaming(engine, source):
    engine.acquire()
    engine.acquire()
    assert wait_until(lambda: engine.get_frame() is not None)

    engine.release()
    time.sleep(0.05)
    before = engine.get_frame()

    assert wait_until(lambda: engine.get_frame(since=before.frame_id) is not None)
    assert source.close_count == 0


def test_last_release_stops_the_thread_and_closes_the_device(engine, source):
    engine.acquire()
    assert wait_until(lambda: engine.get_frame() is not None)

    engine.release()

    assert wait_until(lambda: source.close_count == 1)
    assert engine.status is DepthStatus.IDLE
    # Assert on the engine's own thread reference, not on process-wide thread
    # scanning: test_slow_shutdown_does_not_orphan_a_resurrecting_thread
    # deliberately leaves a "depth-capture" thread alive elsewhere in this
    # process, so a global scan is only kept honest by source-definition
    # ordering -- any reordering (a new test, pytest-randomly, pytest-xdist)
    # would turn this into a flake that reads like a real refcount regression.
    assert engine._thread is None


def test_release_below_zero_is_harmless(engine):
    engine.release()
    engine.release()

    assert engine.status is DepthStatus.IDLE


def test_close_is_idempotent(engine):
    engine.acquire()
    assert wait_until(lambda: engine.get_frame() is not None)

    engine.close()
    engine.close()

    assert engine.status is DepthStatus.IDLE


def test_frame_ids_start_after_the_no_frame_sentinel(engine):
    engine.acquire()
    assert wait_until(lambda: engine.get_frame() is not None)

    assert engine.get_frame().frame_id > NO_FRAME_ID


def test_acquire_after_close_restarts_capture(engine, source):
    """Regression: close() must reset the refcount.

    Previously close() never reset _refcount, so a direct close() while a
    consumer still held a reference left it non-zero. The next acquire()
    would then bump it from 1 to 2, compute should_start=False, and never
    start a thread again -- bricking the engine forever.
    """
    engine.acquire()
    assert wait_until(lambda: engine.get_frame() is not None)

    engine.close()
    assert engine.status is DepthStatus.IDLE

    engine.acquire()

    assert wait_until(lambda: engine.status is DepthStatus.STREAMING)
    assert wait_until(lambda: engine.get_frame() is not None)
    assert source.open_count == 2
    assert any(t.name == "depth-capture" for t in threading.enumerate())


def test_slow_shutdown_does_not_orphan_a_resurrecting_thread(monkeypatch):
    """Regression: a thread stuck past the join timeout must not resurrect.

    Previously _running was a single instance-wide flag: close() gave up on
    joining a slow thread but left it alive, and a later acquire() flipped
    _running back to True -- reviving the *same* orphaned thread, which then
    published frames again and never closed its device. Each thread must
    instead carry its own stop token that stays set for its whole life, and a
    later acquire() must start a genuinely independent session.
    """
    monkeypatch.setattr(depth_engine, "JOIN_TIMEOUT_S", 0.05)

    stuck = SlowReadSource(depth_scale=0.25)
    fresh = FakeSource(depth_scale=0.75)
    sources = iter([stuck, fresh])
    engine = DepthEngine(lambda: next(sources))

    try:
        engine.acquire()
        assert wait_until(lambda: engine.status is DepthStatus.STREAMING)

        engine.close()  # stuck's first read() is still blocked; join times out fast

        assert engine.status is DepthStatus.IDLE
        assert stuck.close_count == 0  # confirmed still blocked, hasn't unwound

        # A later acquire() must start a fresh, independent session.
        engine.acquire()
        assert wait_until(lambda: engine.get_frame() is not None)
        assert engine.get_frame().depth_scale == fresh.depth_scale
        assert stuck.open_count == 1  # never reopened/resurrected

        # Once the stuck read finally returns, its thread must exit quietly
        # -- closing its own device -- rather than resuming publication.
        stuck.release_first_read()
        assert wait_until(lambda: stuck.close_count == 1)

        time.sleep(0.05)
        assert engine.get_frame().depth_scale == fresh.depth_scale
    finally:
        stuck.release_first_read()
        engine.close()


class FailingSource(FakeSource):
    """Fails to open until `fail_opens` attempts have been made."""

    def __init__(self, fail_opens=1, **kwargs):
        super().__init__(**kwargs)
        self.fail_opens = fail_opens
        self.attempts = 0

    def open(self):
        self.attempts += 1
        if self.attempts <= self.fail_opens:
            raise DepthSourceError("device not found")
        return super().open()


class DyingSource(FakeSource):
    """Streams a few frames, then loses the device on every later read."""

    def __init__(self, frames_before_death=3, **kwargs):
        super().__init__(**kwargs)
        self.frames_before_death = frames_before_death

    def read(self):
        if self._counter >= self.frames_before_death:
            raise DepthSourceError("device disconnected")
        return super().read()


def recording_sleep(delays):
    def sleep(seconds):
        delays.append(seconds)
        time.sleep(0.001)  # keep the reconnect loop from spinning hot

    return sleep


def test_failure_to_open_reports_unavailable_with_a_reason():
    source = FailingSource(fail_opens=99)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep([]))
    try:
        engine.acquire()

        assert wait_until(lambda: engine.status is DepthStatus.UNAVAILABLE)
        assert "device not found" in engine.status_reason
    finally:
        engine.close()


def test_a_missing_sdk_is_reported_not_raised():
    def factory():
        raise ImportError("No module named 'pyorbbecsdk'")

    engine = DepthEngine(factory, sleep_fn=recording_sleep([]))
    try:
        engine.acquire()

        assert wait_until(lambda: engine.status is DepthStatus.UNAVAILABLE)
        assert "pyorbbecsdk" in engine.status_reason
    finally:
        engine.close()


def test_open_failures_back_off_exponentially_up_to_the_cap():
    delays = []
    source = FailingSource(fail_opens=99)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep(delays))
    try:
        engine.acquire()

        assert wait_until(lambda: len(delays) >= 6)
    finally:
        engine.close()

    assert delays[0] == INITIAL_BACKOFF_S
    assert delays[1] == INITIAL_BACKOFF_S * 2
    assert delays[2] == INITIAL_BACKOFF_S * 4
    assert all(delay <= MAX_BACKOFF_S for delay in delays)
    assert delays[-1] == MAX_BACKOFF_S


def test_the_engine_recovers_when_the_device_appears():
    source = FailingSource(fail_opens=2)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep([]))
    try:
        engine.acquire()

        assert wait_until(lambda: engine.status is DepthStatus.STREAMING)
        assert wait_until(lambda: engine.get_frame() is not None)
    finally:
        engine.close()


def test_backoff_resets_after_a_successful_read():
    # Renamed from "...after_a_successful_open": backoff means "time since the
    # stream last actually produced a frame", so the reset happens on the
    # first successful read/publish, not on a bare successful open. This
    # FailingSource only ever fails open(), never read(), so the two
    # behaviours aren't distinguishable by this test alone -- see
    # test_read_errors_back_off_before_reconnecting for a case where a handle
    # opens fine but reads keep failing, which only the new contract handles.
    delays = []
    source = FailingSource(fail_opens=2)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep(delays))
    try:
        engine.acquire()
        assert wait_until(lambda: engine.status is DepthStatus.STREAMING)
        assert wait_until(lambda: engine.get_frame() is not None)
    finally:
        engine.close()

    # Two failures: 1s then 2s. Nothing longer, because the third open worked
    # and its first read succeeded.
    assert delays == [INITIAL_BACKOFF_S, INITIAL_BACKOFF_S * 2]


def test_a_read_error_closes_the_device_and_reconnects():
    source = DyingSource(frames_before_death=3)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep([]))
    try:
        engine.acquire()

        assert wait_until(lambda: source.close_count >= 1)
        assert wait_until(lambda: source.open_count >= 2)
    finally:
        engine.close()


def test_read_errors_back_off_before_reconnecting():
    # Regression: a device that opens fine but fails every read (a wedged
    # device, a flaky cable) must be throttled exactly like a failed open --
    # not spin open/read-fail/close hot with backoff never engaging.
    delays = []
    source = DyingSource(frames_before_death=3)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep(delays))
    try:
        engine.acquire()

        assert wait_until(lambda: len(delays) >= 3)
    finally:
        engine.close()

    assert delays[0] == INITIAL_BACKOFF_S
    assert delays[1] == INITIAL_BACKOFF_S * 2
    assert delays[2] == INITIAL_BACKOFF_S * 4
    assert all(delay <= MAX_BACKOFF_S for delay in delays)


def test_an_unplugged_camera_leaves_the_last_frame_readable():
    # The node keeps rendering the last good frame rather than going black the
    # instant the cable is pulled.
    source = DyingSource(frames_before_death=3)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep([]))
    try:
        engine.acquire()
        assert wait_until(lambda: engine.get_frame() is not None)

        assert wait_until(lambda: source.close_count >= 1)

        assert engine.get_frame() is not None
    finally:
        engine.close()


def test_close_does_not_wait_out_a_long_backoff():
    # With no sleep_fn injected the engine waits on its stop token, so close()
    # interrupts the backoff instead of blocking for MAX_BACKOFF_S. Uses the
    # real production path deliberately: injecting a sleep stub here would
    # test the stub, not the shutdown behaviour that matters.
    source = FailingSource(fail_opens=99)
    engine = DepthEngine(lambda: source)
    engine.acquire()

    # Let it fail once and enter the backoff.
    assert wait_until(lambda: source.attempts >= 1)

    started = time.time()
    engine.close()
    elapsed = time.time() - started

    # INITIAL_BACKOFF_S is 1.0 and the cap is 30.0; a blocking sleep would
    # show up as at least a second here.
    assert elapsed < INITIAL_BACKOFF_S, f"close() blocked for {elapsed:.2f}s"
    assert engine.status is DepthStatus.IDLE
