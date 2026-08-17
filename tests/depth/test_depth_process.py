"""The shared-memory transport between the depth child and the render process."""

import time

import numpy as np
import pytest

from depth.depth_process import HEADER_SIZE, FrameRing


@pytest.fixture
def ring():
    r = FrameRing.create(4, 3)
    yield r
    r.close()
    r.unlink()


def make_frame(value, width=4, height=3):
    return np.full((height, width), value, dtype=np.uint16)


def test_a_reader_sees_nothing_before_the_first_write(ring):
    reader = FrameRing.attach(ring.name)
    try:
        frame, seq = reader.read(0)
        assert frame is None
        assert seq == 0
    finally:
        reader.close()


def test_a_written_frame_comes_back_intact(ring):
    reader = FrameRing.attach(ring.name)
    try:
        ring.write(make_frame(1234))
        frame, seq = reader.read(0)

        assert seq != 0
        assert frame.shape == (3, 4)
        assert frame.dtype == np.uint16
        assert (frame == 1234).all()
    finally:
        reader.close()


def test_reading_twice_without_a_write_returns_nothing(ring):
    reader = FrameRing.attach(ring.name)
    try:
        ring.write(make_frame(7))
        _, seq = reader.read(0)
        frame, seq2 = reader.read(seq)

        assert frame is None
        assert seq2 == seq
    finally:
        reader.close()


def test_a_stalled_reader_gets_the_newest_frame_not_the_oldest(ring):
    # Latest-frame-wins is the whole reason this is shared memory rather than
    # a Queue: a backlog of stale depth frames is worse than a dropped one.
    reader = FrameRing.attach(ring.name)
    try:
        for value in (1, 2, 3, 4, 5):
            ring.write(make_frame(value))

        frame, _ = reader.read(0)
        assert (frame == 5).all()
    finally:
        reader.close()


def test_attach_recovers_the_dimensions_from_the_header(ring):
    reader = FrameRing.attach(ring.name)
    try:
        assert reader.width == 4
        assert reader.height == 3
    finally:
        reader.close()


def test_the_returned_frame_is_a_copy_not_a_live_view(ring):
    # The child overwrites slots continuously. A view would mutate under the
    # caller between the read and the texture upload.
    reader = FrameRing.attach(ring.name)
    try:
        ring.write(make_frame(11))
        frame, _ = reader.read(0)
        ring.write(make_frame(22))
        ring.write(make_frame(33))

        assert (frame == 11).all()
    finally:
        reader.close()


def test_a_torn_read_is_retried(ring, monkeypatch):
    # Simulates the writer landing mid-copy: seq moves between the reader's
    # two samples, so the first attempt must be discarded.
    reader = FrameRing.attach(ring.name)
    try:
        ring.write(make_frame(1))
        seen = {"n": 0}
        real = reader._seq

        def flaky():
            seen["n"] += 1
            # Report a different seq on the confirming sample of attempt 1.
            if seen["n"] == 2:
                return real() + 99
            return real()

        monkeypatch.setattr(reader, "_seq", flaky)
        frame, _ = reader.read(0)

        assert frame is not None
        assert seen["n"] > 2
    finally:
        reader.close()


import multiprocessing

from depth.depth_process import _child_main


class FakeSource:
    """Stands in for OrbbecSource inside the child."""

    width, height, scale = 4, 3, 0.5
    fail_on_open = False

    def __init__(self):
        self._value = 0

    def open(self):
        if type(self).fail_on_open:
            from depth.depth_source import DepthSourceError

            raise DepthSourceError("no device here")
        return self.width, self.height, self.scale

    def read(self):
        self._value += 1
        return np.full((self.height, self.width), self._value, dtype=np.uint16)

    def close(self):
        pass


def run_child(source_factory):
    """Drive _child_main in-process on a thread, over a real Pipe pair."""
    import threading

    parent_conn, child_conn = multiprocessing.Pipe()
    thread = threading.Thread(
        target=_child_main, args=(child_conn, source_factory), daemon=True
    )
    thread.start()
    return parent_conn, thread


def test_the_child_reports_dimensions_after_stream():
    conn, thread = run_child(FakeSource)
    try:
        conn.send(("stream",))
        assert conn.poll(5), "child never answered"
        kind, name, width, height, scale = conn.recv()

        assert kind == "ready"
        assert (width, height, scale) == (4, 3, 0.5)
        assert isinstance(name, str) and name
    finally:
        conn.send(("shutdown",))
        thread.join(5)


def test_the_child_publishes_frames_into_the_ring():
    conn, thread = run_child(FakeSource)
    try:
        conn.send(("stream",))
        assert conn.poll(5)
        _, name, _, _, _ = conn.recv()

        reader = FrameRing.attach(name)
        try:
            deadline = time.time() + 5
            frame = None
            while frame is None and time.time() < deadline:
                frame, _ = reader.read(0)
                time.sleep(0.01)

            assert frame is not None, "no frame arrived"
            assert frame.shape == (3, 4)
        finally:
            reader.close()
    finally:
        conn.send(("shutdown",))
        thread.join(5)


def test_a_source_that_cannot_open_is_reported_as_an_error():
    FakeSource.fail_on_open = True
    try:
        conn, thread = run_child(FakeSource)
        try:
            conn.send(("stream",))
            assert conn.poll(5)
            kind, message = conn.recv()

            assert kind == "error"
            assert "no device here" in message
        finally:
            conn.send(("shutdown",))
            thread.join(5)
    finally:
        FakeSource.fail_on_open = False


def test_shutdown_ends_the_child_loop():
    conn, thread = run_child(FakeSource)
    conn.send(("stream",))
    assert conn.poll(5)
    conn.recv()
    conn.send(("shutdown",))
    thread.join(5)

    assert not thread.is_alive()


from depth import depth_process
from depth.depth_process import ProcessSource, _reset_child_for_tests
from depth.depth_source import DepthSourceError


def child_with_fake_source(conn):
    """A child target that serves FakeSource. Must be importable at module
    level, because spawn pickles it by qualified name."""
    _child_main(conn, FakeSource)


@pytest.fixture(autouse=True)
def fresh_child():
    _reset_child_for_tests()
    yield
    _reset_child_for_tests()


def test_open_returns_the_childs_dimensions():
    source = ProcessSource(child_target=child_with_fake_source)
    try:
        assert source.open() == (4, 3, 0.5)
    finally:
        source.close()


def test_read_returns_frames_then_none_until_the_next_one(monkeypatch):
    source = ProcessSource(child_target=child_with_fake_source)
    try:
        source.open()

        deadline = time.time() + 10
        frame = None
        while frame is None and time.time() < deadline:
            frame = source.read()

        assert frame is not None
        assert frame.shape == (3, 4)
        assert frame.dtype == np.uint16

        # "...then None until the next one": once read() has caught up to
        # the ring, a call that sees no new write must return None, not
        # replay the last frame. FakeSource is unpaced -- the child writes
        # far faster than 31fps -- so a second *live* call almost always
        # finds a frame already waiting, which would let this assertion
        # pass by luck rather than by exercising the "no new write" path.
        # Stubbing the ring's read makes "no new write" deterministic, and
        # shrinking READ_TIMEOUT_S keeps the wait milliseconds rather than
        # the full 200ms production budget.
        monkeypatch.setattr(depth_process, "READ_TIMEOUT_S", 0.02)
        last_seq = source._last_seq
        monkeypatch.setattr(source._ring, "read", lambda seq: (None, seq))

        started = time.time()
        assert source.read() is None
        assert time.time() - started < 0.2
        assert source._last_seq == last_seq
    finally:
        source.close()


def test_read_before_open_is_an_error():
    source = ProcessSource(child_target=child_with_fake_source)

    with pytest.raises(DepthSourceError):
        source.read()


def test_open_close_reopen_streams_frames_each_time():
    """Regression: stop_stream used to leave its ("stopped",) reply unread
    on the control pipe, so the next start_stream() would recv() that stale
    reply -- or a stale ("error", ...) -- instead of the answer to its own
    ("stream",) request, and could attach to a shm block the child was
    already unlinking. Three sessions covers "the second and third open()".
    """
    source = ProcessSource(child_target=child_with_fake_source)
    try:
        for session in range(3):
            dims = source.open()
            assert dims == (4, 3, 0.5), "session %d got %r" % (session, dims)

            deadline = time.time() + 10
            frame = None
            while frame is None and time.time() < deadline:
                frame = source.read()

            assert frame is not None, "session %d: no frame arrived" % session
            source.close()
    finally:
        source.close()


def test_close_on_a_stale_instance_does_not_stop_the_current_session():
    """Regression: close() used to stop the module-level singleton
    unconditionally, so a slow-to-unwind stale ProcessSource could tear down
    a stream a newer ProcessSource had already started (and unlink the shm
    block it had just attached to) -- same symptom as the pipe-desync bug
    above, different trigger, and it survives fixing that one.
    """
    stale = ProcessSource(child_target=child_with_fake_source)
    stale.open()

    current = ProcessSource(child_target=child_with_fake_source)
    current.open()

    stale.close()

    try:
        deadline = time.time() + 10
        frame = None
        while frame is None and time.time() < deadline:
            frame = current.read()

        assert frame is not None, "current session died after a stale close()"
    finally:
        current.close()
