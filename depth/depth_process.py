"""Depth capture in a child process, so its GIL cost cannot stall rendering.

The Orbbec filter chain holds the GIL for about 68% of the 14.5 ms it spends
on each frame. At 31 fps that is roughly 306 ms a second during which no other
Python in the process can run -- including the render loop. Measured against
the real camera, in-process capture costs 5 fps and pushes the p99 frame
interval from 15.6 ms to 22.7 ms.

A child process has its own GIL, so the filters stop competing with rendering
and all five can be kept rather than traded away for frame rate.
"""

import atexit
import multiprocessing
import time
from multiprocessing import shared_memory

import numpy as np

from depth.depth_source import DepthSource, DepthSourceError

# Frame slots start here. One page, far more than the header needs, so the
# slots land on a page boundary and the layout stays readable in a hex dump.
HEADER_SIZE = 4096

# Header fields, as indices into a uint32 view of the first bytes.
_SEQ = 0
_SLOT = 1
_WIDTH = 2
_HEIGHT = 3

# uint32 seq wraps after 2**32 frames, which is over four years at 31 fps.
_SEQ_MODULO = 1 << 32

# A read retries only if the writer landed mid-copy. At 31 fps against a copy
# measured in microseconds that is vanishingly rare, so a low cap is honest:
# if it ever exhausts, something is wrong and returning None is correct.
_READ_ATTEMPTS = 4


class FrameRing:
    """Double-buffered uint16 frames in shared memory, newest-wins.

    One writer (the child) and one reader (the render process), coordinated by
    a sequence counter rather than a lock: the writer fills the slot the reader
    is not looking at, publishes it, then bumps `seq`. The reader samples `seq`,
    copies, and re-samples; a change means the writer overtook it mid-copy and
    the attempt is discarded.

    Deliberately not a Queue. A queue would buffer stale depth frames whenever
    the reader fell behind, and for live visuals the newest frame is the only
    one worth having.
    """

    def __init__(self, shm, width, height):
        self._shm = shm
        self.name = shm.name
        self.width = width
        self.height = height

        frame_bytes = width * height * 2
        self._header = np.ndarray((4,), dtype=np.uint32, buffer=shm.buf)
        self._slots = [
            np.ndarray(
                (height, width),
                dtype=np.uint16,
                buffer=shm.buf,
                offset=HEADER_SIZE + index * frame_bytes,
            )
            for index in (0, 1)
        ]

    @classmethod
    def create(cls, width, height):
        size = HEADER_SIZE + 2 * width * height * 2
        shm = shared_memory.SharedMemory(create=True, size=size)
        ring = cls(shm, width, height)
        ring._header[_SEQ] = 0
        ring._header[_SLOT] = 0
        ring._header[_WIDTH] = width
        ring._header[_HEIGHT] = height
        return ring

    @classmethod
    def attach(cls, name):
        shm = shared_memory.SharedMemory(name=name)

        # Deliberately left registered with the resource_tracker. On the
        # normal path the creator's unlink() clears this block's entry, so
        # attaching here warns about nothing. On the abnormal path -- the
        # creator dies before it unlinks -- the tracker's "leaked shared_memory
        # objects" warning is the honest signal that a block was orphaned, not
        # noise to be suppressed.

        header = np.ndarray((4,), dtype=np.uint32, buffer=shm.buf)
        return cls(shm, int(header[_WIDTH]), int(header[_HEIGHT]))

    def _seq(self):
        return int(self._header[_SEQ])

    def write(self, frame):
        """Publish a frame. Only the child calls this."""
        slot = 1 - int(self._header[_SLOT])
        self._slots[slot][:] = frame
        self._header[_SLOT] = slot
        self._header[_SEQ] = (self._seq() + 1) % _SEQ_MODULO

    def read(self, last_seq):
        """The newest frame if it is not `last_seq`, else (None, last_seq)."""
        for _ in range(_READ_ATTEMPTS):
            seq = self._seq()

            if seq == last_seq:
                return None, last_seq

            slot = int(self._header[_SLOT])
            # Copy: the writer will overwrite this slot, and the caller holds
            # the array until it reaches the GPU.
            frame = self._slots[slot].copy()

            if self._seq() == seq:
                return frame, seq

        return None, last_seq

    def close(self):
        """Detach. Both sides call this; only the creator unlinks."""
        self._header = None
        self._slots = []
        self._shm.close()

    def unlink(self):
        """Destroy the block. Only the creating process calls this."""
        self._shm.unlink()


# How long the child waits on the control pipe between capture attempts while
# it is idle. Short enough that a shutdown is not perceptible, long enough that
# an idle child costs nothing.
POLL_INTERVAL_S = 0.05


def _child_main(conn, source_factory=None):
    """Run capture and publish frames. The entry point of the child process.

    Deliberately thin: it owns no capture logic of its own, only a loop around
    the source it is handed. That source is OrbbecSource -- the same class,
    with the same profile selection, the same filter chain and the same error
    messages that ran in-process before. Capture was relocated, not rewritten.
    """
    if source_factory is None:
        from depth.depth_source import OrbbecSource

        source_factory = OrbbecSource

    source = None
    ring = None

    def teardown():
        nonlocal source, ring
        if source is not None:
            try:
                source.close()
            except Exception:
                pass
            source = None
        if ring is not None:
            ring.close()
            try:
                ring.unlink()
            except FileNotFoundError:
                pass
            ring = None

    try:
        while True:
            if conn.poll(POLL_INTERVAL_S if source is None else 0):
                try:
                    message = conn.recv()
                except EOFError:
                    # The parent died. Nothing left to serve.
                    break

                command = message[0]

                if command == "shutdown":
                    break

                if command == "stop":
                    teardown()
                    conn.send(("stopped",))
                    continue

                if command == "stream":
                    teardown()
                    try:
                        source = source_factory()
                        width, height, scale = source.open()
                        ring = FrameRing.create(width, height)
                    except Exception as error:
                        teardown()
                        conn.send(("error", str(error)))
                        continue

                    conn.send(("ready", ring.name, width, height, scale))

            if source is None:
                continue

            try:
                frame = source.read()
            except Exception as error:
                teardown()
                conn.send(("error", str(error)))
                continue

            if frame is not None:
                ring.write(frame)
    finally:
        teardown()
        try:
            conn.close()
        except Exception:
            pass


# How long open() waits for the child to report. A cold child pays a fresh
# interpreter, the pyorbbecsdk import and the camera open; 15 s is generous
# for all three and still bounded. This wait happens on DepthEngine's capture
# thread, never on the GUI thread, so rendering is unaffected by it.
OPEN_TIMEOUT_S = 15.0

# How long stop_stream waits for the child's ("stopped",) reply before giving
# up on it. The reply's content is unused; consuming it is what matters, so
# that the next start_stream() never inherits it as a stale, mismatched
# answer to a different request. 2 s is generous for a teardown that is only
# closing a device handle, not opening one.
STOP_TIMEOUT_S = 2.0

_child = None


class _Child:
    """Owns the capture process across ProcessSource instances.

    DepthEngine builds a fresh source from the factory on every retry, so the
    process cannot belong to a ProcessSource: a release/re-acquire cycle would
    kill and respawn it, and a live session cycling through states would pay
    seconds of black depth each time.

    Module-level state, which is the ugly part of this design. Killing the
    child on every release would be cleaner code and worse behaviour.
    """

    def __init__(self, target):
        self.target = target
        self.process = None
        self.conn = None
        # The shm name of the stream currently running, or None. This is the
        # session token ProcessSource.close() checks against: the _Child
        # object itself stays the same instance across every session on the
        # same target (that is the whole point of the singleton), so object
        # identity alone cannot tell "my session" from "a newer session that
        # reused this same singleton" -- see ProcessSource.close().
        self.session = None

    def alive(self):
        return self.process is not None and self.process.is_alive()

    def ensure_started(self):
        if self.alive():
            return

        self.shutdown()

        # spawn, never fork: forking a process holding a GL context, Qt state
        # and an open camera is exactly the class of intermittent failure this
        # work exists to remove.
        context = multiprocessing.get_context("spawn")
        self.conn, child_conn = context.Pipe()
        self.process = context.Process(
            target=self.target, args=(child_conn,), name="depth-capture", daemon=True
        )
        self.process.start()
        # Close the parent's duplicate of the child's pipe end. Process death
        # would close it regardless, so that is not the reason: leaving it
        # open leaks an fd in the parent on every respawn, and it is what
        # would keep the pipe alive from the child's perspective if the
        # parent ever closes self.conn (shutdown(), a crash during teardown)
        # without the process itself dying -- the child would then never see
        # EOF on its end.
        child_conn.close()

    def start_stream(self):
        self.ensure_started()

        try:
            # Discard anything already sitting on the pipe. stop_stream
            # normally consumes its own ("stopped",) reply, but a session
            # that ended abnormally (a dead child, a send that raced a
            # shutdown) can still leave one behind. Without this drain, that
            # leftover message would be mistaken for *this* request's reply
            # below and the control channel would never resynchronise --
            # every close/open cycle would leave one more unmatched message
            # on the pipe than the last.
            while self.conn.poll(0):
                self.conn.recv()

            self.conn.send(("stream",))

            if not self.conn.poll(OPEN_TIMEOUT_S):
                raise DepthSourceError(
                    "depth process did not report within %ss" % OPEN_TIMEOUT_S
                )

            message = self.conn.recv()
        except (OSError, EOFError) as error:
            raise DepthSourceError("depth process went away: %s" % error) from error

        if message[0] == "error":
            raise DepthSourceError(message[1])

        if message[0] != "ready":
            raise DepthSourceError(
                "unexpected message from depth process: %r" % (message,)
            )

        self.session = message[1]

        return message[1], message[2], message[3], message[4]

    def stop_stream(self):
        self.session = None
        if not self.alive():
            return
        try:
            self.conn.send(("stop",))
            # Consume the child's ("stopped",) reply here, rather than
            # leaving it on the pipe: it is the read of this reply -- not the
            # send above -- that keeps the channel request/response-correct,
            # so the next start_stream() never mistakes it for its own.
            if self.conn.poll(STOP_TIMEOUT_S):
                self.conn.recv()
        except (BrokenPipeError, OSError, EOFError):
            pass

    def shutdown(self):
        if self.process is not None:
            try:
                if self.process.is_alive():
                    self.conn.send(("shutdown",))
                    self.process.join(2.0)
            except (BrokenPipeError, OSError):
                pass

            if self.process.is_alive():
                self.process.terminate()
                self.process.join(1.0)

            if self.process.is_alive():
                # SIGTERM was ignored or the child was too wedged to act on
                # it. SIGKILL cannot be caught or blocked, so this always
                # ends the process; the cost is the accepted gap documented
                # on FrameRing.attach -- a killed child orphans its shm
                # segment, which the resource tracker's leak warning is left
                # to surface rather than being cleaned up here.
                self.process.kill()
                self.process.join(0.5)

        if self.conn is not None:
            try:
                self.conn.close()
            except OSError:
                pass

        self.process = None
        self.conn = None
        self.session = None


def _get_child(target):
    global _child

    if _child is None or _child.target is not target:
        if _child is not None:
            _child.shutdown()
        _child = _Child(target)

    return _child


def _reset_child_for_tests():
    """Tear down the singleton. Tests only."""
    global _child

    if _child is not None:
        _child.shutdown()
        _child = None


def _shutdown_at_exit():
    _reset_child_for_tests()


atexit.register(_shutdown_at_exit)


# Matches OrbbecSource.READ_TIMEOUT_MS (200 ms), so DepthEngine's capture
# loop paces itself identically no matter which source it holds: read()
# blocks until a frame arrives or this budget expires, rather than returning
# instantly. A read() that returned instantly was measured, in DepthEngine's
# exact loop shape (`if frame is None: continue`, no sleep of its own), at
# 1.68M calls/s -- a saturated GIL consumer sitting in the parent process,
# putting back the exact contention this task exists to remove. The sleep
# between polls below is what releases the GIL; that release is the point,
# not the 2ms figure. At 31fps a frame lands roughly every 32ms, so in normal
# streaming read() returns almost immediately and this budget is only ever
# spent once frames actually stop arriving.
READ_TIMEOUT_S = 0.2

# Granularity of the wait inside read(). Short enough that a frame landing
# just after a poll is still noticed promptly; long enough that the poll
# itself is not what saturates the GIL in its place.
_READ_POLL_INTERVAL_S = 0.002


class ProcessSource(DepthSource):
    """A DepthSource whose capture runs in another process.

    Implements the same three methods as OrbbecSource, so DepthEngine,
    DepthInput and DepthStatus need no knowledge that anything changed.
    """

    def __init__(self, child_target=None):
        self._target = child_target or _default_child_target
        self._ring = None
        self._last_seq = 0
        # The singleton _Child this instance's open() actually started a
        # stream on, and that stream's session token, if any. Both are
        # recorded so close() can tell "my session" from "whatever session
        # happens to be current" -- see close() below. The _Child object
        # alone cannot answer that: it is the same instance across every
        # session on the same target.
        self._child = None
        self._session = None

    def open(self):
        child = _get_child(self._target)
        name, width, height, scale = child.start_stream()
        # Recorded as soon as the child confirms it is streaming for us --
        # not after the attach below -- so that if attach fails we still
        # know this instance owns the session and can stop it (see the
        # except clause) rather than leaking a live child with no reader.
        self._child = child
        self._session = name

        try:
            self._ring = FrameRing.attach(name)
        except OSError as error:
            # The most likely cause is the child having already unlinked
            # this block -- e.g. a stale reply from a torn-down session (see
            # start_stream's drain) pointed at a name that no longer exists.
            # Only stop the stream if it is still *our* session (child.session
            # still equals the name we were handed): two overlapping open()
            # calls -- a stale caller still inside a cold start_stream() while
            # a newer one has already replaced it -- would otherwise let this
            # unconditionally kill a session that is not ours to stop, the
            # same failure Important 2 fixed for close().
            if child.session == name:
                child.stop_stream()
            self._child = None
            self._session = None
            raise DepthSourceError("depth process went away: %s" % error) from error

        self._last_seq = 0

        return width, height, scale

    def read(self):
        if self._ring is None:
            raise DepthSourceError("read() on a ProcessSource that is not open")

        frame, seq = self._ring.read(self._last_seq)
        if frame is not None:
            self._last_seq = seq
            return frame

        deadline = time.monotonic() + READ_TIMEOUT_S
        while time.monotonic() < deadline:
            time.sleep(_READ_POLL_INTERVAL_S)
            frame, seq = self._ring.read(self._last_seq)
            if frame is not None:
                self._last_seq = seq
                return frame

        return None

    def close(self):
        # Only stop the stream if this instance is the one that started the
        # session the singleton is currently running -- otherwise a
        # slow-to-unwind stale instance (see DepthEngine.close's
        # JOIN_TIMEOUT_S) would tear down a session a newer ProcessSource has
        # already opened, killing its stream and unlinking its shm block out
        # from under it. Checking self._child is _child alone is not enough:
        # the singleton is the same object across every session on the same
        # target, so the session token (self._session vs. child.session) is
        # what actually distinguishes them.
        owns_current_session = (
            self._child is not None
            and self._child is _child
            and self._session == self._child.session
        )

        if self._ring is not None:
            self._ring.close()
            self._ring = None

        if owns_current_session:
            self._child.stop_stream()

        self._child = None
        self._session = None


def _default_child_target(conn):
    """Module-level so spawn can pickle it by qualified name."""
    _child_main(conn)
