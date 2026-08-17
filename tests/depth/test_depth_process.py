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
        # Wrapped modulo uint16's range: FakeSource is unpaced and a
        # multi-second test can drive it past 65536 reads, where an
        # unwrapped counter would overflow the frame's uint16 dtype and
        # raise inside the child, silently ending the stream.
        self._value = (self._value + 1) % 65536
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

        # Bounded above (does not idle out past the shrunk budget) and below
        # (actually blocks for it rather than returning instantly, which is
        # Critical 2's whole point -- an instant return here would busy-spin
        # DepthEngine's capture loop in production and no other test would
        # catch it, since every other assertion in this file only cares that
        # a frame eventually arrives).
        started = time.monotonic()
        assert source.read() is None
        elapsed = time.monotonic() - started
        assert elapsed >= 0.02
        assert elapsed < 0.2
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
        # Let the stray ("stop",) -- if the bug is present -- actually land
        # and take effect, rather than racing it.
        time.sleep(0.3)

        # Drain whatever the child buffered into the ring before/around the
        # stray stop: with the bug present the child unlinked the ring and
        # exited its capture loop, but frames already written before that are
        # still readable, so a single catch-up read must not be mistaken for
        # "still streaming".
        current.read()

        deadline = time.time() + 10
        frame = None
        while frame is None and time.time() < deadline:
            frame = current.read()

        assert frame is not None, "current session died after a stale close()"
    finally:
        current.close()


def child_that_exits(conn):
    """Answers 'stream' normally, then dies."""
    ring = FrameRing.create(4, 3)
    conn.send(("ready", ring.name, 4, 3, 1.0))
    time.sleep(0.2)
    ring.close()


def child_that_goes_silent(conn):
    """Answers 'stream', publishes one frame, then never publishes again."""
    ring = FrameRing.create(4, 3)
    conn.send(("ready", ring.name, 4, 3, 1.0))
    ring.write(np.full((3, 4), 5, dtype=np.uint16))
    while True:
        time.sleep(0.1)


def test_a_dead_child_is_reported_as_a_source_error():
    source = ProcessSource(child_target=child_that_exits)
    try:
        source.open()

        deadline = time.time() + 10
        with pytest.raises(DepthSourceError, match="depth process"):
            while time.time() < deadline:
                source.read()
                time.sleep(0.05)
            pytest.fail("read() never raised after the child exited")
    finally:
        source.close()


def test_a_silent_child_trips_the_wedge_timeout(monkeypatch):
    monkeypatch.setattr(depth_process, "WEDGE_TIMEOUT_S", 0.5)
    source = ProcessSource(child_target=child_that_goes_silent)
    try:
        source.open()

        deadline = time.time() + 10
        with pytest.raises(DepthSourceError, match="no depth frame"):
            while time.time() < deadline:
                source.read()
                time.sleep(0.05)
            pytest.fail("read() never raised for a silent child")
    finally:
        source.close()


class PacedFakeSource(FakeSource):
    """Like FakeSource, but sleeps between frames so read()'s bounded wait
    genuinely expires at least once between writes.

    Unpaced FakeSource produces so fast that read()'s pre-loop early-out
    almost always finds a fresh frame immediately -- the "no frame within the
    blocking budget" branch, which is the only branch that consults
    self._last_frame_at, is essentially never reached. That made the wedge
    timer's continuous-production test unable to fail on the bug it names:
    deleting both `self._last_frame_at = time.monotonic()` lines from
    read() still let it pass. Pacing writes slower than the (shrunk)
    READ_TIMEOUT_S below forces every read() to actually reach that branch.
    """

    interval_s = 0.1

    def read(self):
        time.sleep(self.interval_s)
        return super().read()


def child_with_paced_fake_source(conn):
    _child_main(conn, PacedFakeSource)


def test_a_frame_resets_the_wedge_timer(monkeypatch):
    monkeypatch.setattr(depth_process, "WEDGE_TIMEOUT_S", 1.0)
    # Shrink the per-read blocking budget well below PacedFakeSource's 0.1s
    # write interval, so read() must fall through to the "no frame within
    # the budget" branch between every pair of frames -- the branch that
    # actually consults self._last_frame_at -- rather than almost always
    # catching a fresh frame in the pre-loop early-out and never touching it.
    monkeypatch.setattr(depth_process, "READ_TIMEOUT_S", 0.02)
    monkeypatch.setattr(depth_process, "_READ_POLL_INTERVAL_S", 0.002)

    source = ProcessSource(child_target=child_with_paced_fake_source)
    try:
        source.open()

        # PacedFakeSource writes roughly every 0.1s -- comfortably inside the
        # 1s wedge timeout -- so 2s of reading must not trip it. Recording
        # every distinct self._last_frame_at seen proves read() keeps
        # updating it on each new frame (not just that no exception happens
        # to be raised); combined with the timeout not firing despite the
        # no-frame branch running on nearly every call, it also proves the
        # wedge check downstream is actually consuming that updated value
        # rather than a stale one.
        seen = set()
        deadline = time.time() + 2.0
        while time.time() < deadline:
            source.read()
            seen.add(source._last_frame_at)
            time.sleep(0.02)

        assert len(seen) > 1, "self._last_frame_at never advanced"
    finally:
        source.close()


def test_a_frame_found_in_the_blocking_wait_resets_the_wedge_timer(monkeypatch):
    """The wedge timer's *blocking-loop* reset, specifically.

    read() sets self._last_frame_at in two places: the pre-loop early-out and
    the blocking wait. The test above covers the early-out -- deleting that
    line makes it fail -- but not the blocking wait, because PacedFakeSource
    lands frames in whichever of the two happens to be running, so the
    early-out alone keeps _last_frame_at advancing. The blocking wait is the
    production-dominant path: at 31 fps against a 200 ms budget the engine
    almost always ends up there, so a regression on that line would fire the
    wedge every WEDGE_TIMEOUT_S during perfectly healthy streaming, with the
    suite green.

    Stubbing the ring pins which path answers: nothing on the first (early-out)
    call, a frame on the second, which can only be the loop's.
    """
    monkeypatch.setattr(depth_process, "READ_TIMEOUT_S", 0.2)
    monkeypatch.setattr(depth_process, "_READ_POLL_INTERVAL_S", 0.002)

    source = ProcessSource(child_target=child_with_fake_source)
    try:
        source.open()

        calls = {"n": 0}
        published = make_frame(7)

        def staged_read(last_seq):
            calls["n"] += 1
            if calls["n"] == 1:
                return None, last_seq
            return published, last_seq + 1

        monkeypatch.setattr(source._ring, "read", staged_read)

        # Old enough that the wedge check would fire on it, so an unrefreshed
        # timestamp is unmistakable rather than a sub-millisecond difference.
        source._last_frame_at = time.monotonic() - 1000.0
        before = source._last_frame_at

        frame = source.read()

        assert frame is not None
        assert calls["n"] >= 2, "the frame came from the early-out, not the wait"
        assert (
            source._last_frame_at > before
        ), "a frame from the blocking wait did not reset the wedge timer"
    finally:
        source.close()


def test_reopening_reuses_the_same_process():
    # A live session cycling through states releases and re-acquires the
    # engine. Respawning there would cost a fresh interpreter, the SDK import
    # and a camera open -- seconds of black depth, mid-set.
    first = ProcessSource(child_target=child_with_fake_source)
    first.open()
    pid = depth_process._child.process.pid
    first.close()

    second = ProcessSource(child_target=child_with_fake_source)
    try:
        second.open()
        assert depth_process._child.process.pid == pid
    finally:
        second.close()


def test_a_dead_child_is_replaced_on_the_next_open():
    source = ProcessSource(child_target=child_with_fake_source)
    source.open()
    pid = depth_process._child.process.pid
    depth_process._child.process.terminate()
    depth_process._child.process.join(5)
    source.close()

    replacement = ProcessSource(child_target=child_with_fake_source)
    try:
        replacement.open()
        assert depth_process._child.process.pid != pid
        assert depth_process._child.alive()
    finally:
        replacement.close()


def test_close_does_not_kill_the_process():
    source = ProcessSource(child_target=child_with_fake_source)
    source.open()
    source.close()

    assert depth_process._child.alive()


import threading


class SlowOpenFakeSource(FakeSource):
    """Takes long enough to open that two open() calls genuinely overlap.

    A cold open in production (spawn, SDK import, camera) takes seconds, which
    is longer than DepthEngine.close()'s JOIN_TIMEOUT_S: the abandoned capture
    thread is still inside open() when the next acquire() starts a new one.
    """

    open_delay_s = 0.2

    def open(self):
        time.sleep(self.open_delay_s)
        return super().open()


def child_with_slow_open_source(conn):
    _child_main(conn, SlowOpenFakeSource)


# How many times the two-thread scenario below is replayed. The bug it pins is
# a data race, so one round can pass by luck: measured against the unlocked
# code a single round failed roughly one run in three, five rounds every run.
_CONCURRENT_OPEN_ROUNDS = 5


def _open_from_two_threads():
    """Overlap two open() calls the way a state switch does, and report both.

    The second thread starts while the first is already blocked waiting for
    the child's reply -- that is the production shape: DepthEngine.close()
    abandons its capture thread mid-open after JOIN_TIMEOUT_S and a following
    acquire() starts another one on the same singleton.
    """
    barrier = threading.Barrier(2)
    results = {}

    def worker(index):
        source = ProcessSource(child_target=child_with_slow_open_source)
        results[index] = [source, None]
        barrier.wait()
        if index == 1:
            time.sleep(SlowOpenFakeSource.open_delay_s / 2)
        try:
            source.open()
        except (
            Exception
        ) as error:  # noqa: BLE001 -- an unpickling error is a failure too
            results[index][1] = error

    threads = [threading.Thread(target=worker, args=(index,)) for index in (0, 1)]
    for thread in threads:
        thread.start()

    # Two serialised slow opens are well under a second. Ten is generous for
    # that and far below OPEN_TIMEOUT_S, so a thread still running here means
    # the pipe wedged rather than merely queued.
    for thread in threads:
        thread.join(10)

    return threads, [results[index] for index in sorted(results)]


def test_two_threads_opening_at_once_leave_exactly_one_live_session():
    """Regression: the control pipe had no mutual exclusion.

    Two capture threads is ordinary use, not an exotic race -- DepthEngine
    gives up joining its capture thread after JOIN_TIMEOUT_S and a following
    acquire() immediately starts another, while a cold open takes longer than
    that. Unserialised, the two recv() calls on one multiprocessing.Connection
    either steal each other's replies (both open() calls succeed, one of them
    attached to a ring the child has already torn down -- frozen depth
    reported as STREAMING) or split a 4-byte length header from its payload,
    which raises UnpicklingError, loses framing for good and leaves both
    threads blocked inside recv() forever.

    Four things must hold: both opens finish, neither fails, exactly one
    instance owns the session the child is actually running, and that instance
    gets frames.
    """
    for round_index in range(_CONCURRENT_OPEN_ROUNDS):
        threads, results = _open_from_two_threads()
        sources = [source for source, _ in results]

        try:
            assert not any(thread.is_alive() for thread in threads), (
                "round %d: an open() never returned -- the control pipe wedged"
                % round_index
            )

            errors = [error for _, error in results]
            assert errors == [None, None], "round %d: an open() failed: %r" % (
                round_index,
                errors,
            )

            child = depth_process._child
            owners = [
                source
                for source in sources
                if source._session is not None and source._session == child.session
            ]
            assert (
                len(owners) == 1
            ), "round %d: %d of 2 instances believe they own the live session" % (
                round_index,
                len(owners),
            )

            # The survivor is a working stream, not a ring the child already
            # unlinked: the pre-fix failure was two *apparently* successful
            # opens, and in half the reproductions the dead one was the newer
            # session -- the one the engine cares about.
            owner = owners[0]
            deadline = time.time() + 10
            frame = None
            while frame is None and time.time() < deadline:
                frame = owner.read()

            assert frame is not None, (
                "round %d: the surviving session produced no frames" % round_index
            )
        finally:
            for source in sources:
                source.close()


import os
import tempfile

# The child is a real process, so it cannot report back through shared test
# state. A file it touches on close() is the simplest cross-process signal.
CLOSE_MARKER = os.path.join(tempfile.gettempdir(), "patanode-depth-source-closed")


class HangingOpenSource(FakeSource):
    """Still opening when the parent's open timeout expires."""

    open_delay_s = 1.0

    def open(self):
        time.sleep(self.open_delay_s)
        return super().open()

    def close(self):
        with open(CLOSE_MARKER, "w") as marker:
            marker.write("closed")


def child_with_hanging_open_source(conn):
    _child_main(conn, HangingOpenSource)


def test_a_timed_out_open_does_not_leave_the_child_streaming(monkeypatch):
    """Regression: a timed-out start_stream told the child nothing.

    open() then never recorded the child, so close() computed
    owns_current_session as False and sent no stop either. The child finished
    opening into a stream nobody would ever read -- a claimed USB device and a
    burned core for the life of the app.
    """
    monkeypatch.setattr(depth_process, "OPEN_TIMEOUT_S", 0.2)

    if os.path.exists(CLOSE_MARKER):
        os.unlink(CLOSE_MARKER)

    source = ProcessSource(child_target=child_with_hanging_open_source)
    try:
        with pytest.raises(DepthSourceError):
            source.open()

        # The child is still inside its slow open at this point; the stop only
        # takes effect once it comes back out.
        deadline = time.time() + 10
        while not os.path.exists(CLOSE_MARKER) and time.time() < deadline:
            time.sleep(0.05)

        assert os.path.exists(
            CLOSE_MARKER
        ), "the child kept the camera open after the parent gave up on it"
    finally:
        source.close()
        if os.path.exists(CLOSE_MARKER):
            os.unlink(CLOSE_MARKER)


class RecordingConnection:
    """A control pipe that records any two threads using it at once.

    The outcome test above is a race: replayed against the unlocked code a
    single round failed about one run in three, five rounds about one run in
    two, because two unsynchronised recv() calls often happen to pick up the
    right messages anyway. This watches the invariant itself -- one thread on
    the connection at a time -- which either holds or does not, with no luck
    involved once the two threads genuinely overlap.
    """

    def __init__(self, conn):
        self._conn = conn
        self._guard = threading.Lock()
        self._in_flight = set()
        self.overlaps = []

    def _call(self, name, method, *args):
        thread = threading.current_thread().name
        with self._guard:
            if self._in_flight:
                self.overlaps.append((name, thread, sorted(self._in_flight)))
            self._in_flight.add(thread)
        try:
            return method(*args)
        finally:
            with self._guard:
                self._in_flight.discard(thread)

    def poll(self, *args):
        return self._call("poll", self._conn.poll, *args)

    def recv(self):
        return self._call("recv", self._conn.recv)

    def send(self, message):
        return self._call("send", self._conn.send, message)

    def close(self):
        return self._conn.close()

    def fileno(self):
        return self._conn.fileno()


def test_the_control_pipe_is_never_used_by_two_threads_at_once():
    """The serialisation itself, rather than one sampling of its consequences.

    multiprocessing.Connection is not thread-safe: overlapping recv() calls
    split a length header from its payload and framing is then lost for good,
    with both threads blocked inside recv() for the life of the app. The
    second thread below enters while the first is parked waiting on the
    child's reply, so any un-serialised access shows up here every run.
    """
    child = depth_process._get_child(child_with_slow_open_source)
    child.ensure_started()
    recorder = RecordingConnection(child.conn)
    child.conn = recorder

    threads, results = _open_from_two_threads()
    try:
        assert not any(
            thread.is_alive() for thread in threads
        ), "an open() never returned -- the control pipe wedged"
        assert (
            recorder.overlaps == []
        ), "two threads used the control pipe at once: %r" % (recorder.overlaps[:3],)
    finally:
        for source, _ in results:
            source.close()


class DyingSource(FakeSource):
    """Streams for a moment, then fails the way a yanked USB cable does.

    Timed rather than counted, and paced: an unpaced source that failed after
    three frames could tear the ring down before the parent's open() had even
    attached to it, which is a different failure from the one under test.
    """

    alive_s = 0.5
    interval_s = 0.01

    def __init__(self):
        super().__init__()
        self._dies_at = time.monotonic() + self.alive_s

    def read(self):
        time.sleep(self.interval_s)
        if time.monotonic() > self._dies_at:
            from depth.depth_source import DepthSourceError as SourceError

            raise SourceError("device disconnected")
        return super().read()


def child_with_dying_source(conn):
    _child_main(conn, DyingSource)


def test_a_child_side_read_failure_is_reported_without_waiting_out_the_wedge(
    monkeypatch,
):
    """Regression: the child reported the failure instantly and read() ignored
    it, so recovery waited out the full WEDGE_TIMEOUT_S -- measured at ~6 s of
    frozen depth still reported as STREAMING, with the answer sitting unread
    on the control pipe the whole time.

    WEDGE_TIMEOUT_S is raised well above this test's own deadline, so the
    wedge cannot be what rescues it: either read() consults the pipe, or the
    test fails.
    """
    monkeypatch.setattr(depth_process, "WEDGE_TIMEOUT_S", 60.0)
    monkeypatch.setattr(depth_process, "READ_TIMEOUT_S", 0.02)

    source = ProcessSource(child_target=child_with_dying_source)
    try:
        source.open()

        deadline = time.time() + 10
        with pytest.raises(DepthSourceError, match="device disconnected"):
            while time.time() < deadline:
                source.read()
            pytest.fail("read() never surfaced the child's error report")
    finally:
        source.close()
