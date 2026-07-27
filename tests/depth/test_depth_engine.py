import threading
import time

import numpy as np
import pytest

from depth.depth_engine import NO_FRAME_ID, DepthEngine, DepthStatus


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
    assert not any(t.name == "depth-capture" for t in threading.enumerate())


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
