"""App-level depth capture service.

Owns one background thread that pulls frames from a DepthSource and publishes
the newest one into a single slot. Nodes pull from that slot at their own rate;
frames they miss are dropped.

Latest-wins rather than a queue, deliberately: the camera runs at 10fps and the
render loop far faster, and a stalled render thread must not be able to grow a
backlog of stale frames.

A plain threading.Thread, not a QThread. This module stays free of Qt so it can
be exercised without a QApplication, and Qt signal delivery would hand over
every frame -- defeating the drop policy. It matches the existing background
services in artnet/controller.py and server/server.py.
"""

import threading
import time
from collections import namedtuple
from enum import Enum


class DepthStatus(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    UNAVAILABLE = "unavailable"


Frame = namedtuple("Frame", "frame_id data width height depth_scale")

NO_FRAME_ID = 0
JOIN_TIMEOUT_S = 2.0
INITIAL_BACKOFF_S = 1.0

# A failed open() blocks in the SDK for a couple of seconds holding the GIL,
# which stalls the render thread. With no camera attached that cost is paid
# once per retry forever, so the cap is set by how often a visible hitch is
# tolerable rather than by how fast we want to notice a replug: 30s means a
# stall every 30s instead of every 5s. Reconnect latency after plugging the
# camera back in is bounded by this, which is the deliberate trade.
MAX_BACKOFF_S = 30.0


class DepthEngine:
    def __init__(self, source_factory, sleep_fn=time.sleep):
        self._source_factory = source_factory
        self._sleep_fn = sleep_fn

        self._lock = threading.Lock()
        self._slot = None
        self._frame_id = NO_FRAME_ID

        self._status = DepthStatus.IDLE
        self._status_reason = "not started"

        self._refcount = 0
        self._thread = None
        # Each capture thread gets its own stop token (see _start/_run) rather
        # than sharing one instance-wide flag. A thread that is still
        # unwinding -- e.g. blocked in a slow read() past the join timeout --
        # keeps its own token set forever, so it cannot be resurrected by a
        # later acquire() installing a new one, and it never mistakes a fresh
        # session's token for its own.
        self._stop_event = None

    @property
    def status(self):
        with self._lock:
            return self._status

    @property
    def status_reason(self):
        with self._lock:
            return self._status_reason

    def acquire(self):
        """Register a consumer. The first one starts the capture thread."""
        with self._lock:
            self._refcount += 1
            should_start = self._refcount == 1

        if should_start:
            self._start()

    def release(self):
        """Deregister a consumer. The last one stops the capture thread."""
        with self._lock:
            if self._refcount == 0:
                return
            self._refcount -= 1
            should_stop = self._refcount == 0

        if should_stop:
            self.close()

    def get_frame(self, since=NO_FRAME_ID):
        """Newest frame, or None if nothing newer than `since` exists.

        The returned array is never mutated after publication, so the caller may
        read it outside the lock.
        """
        with self._lock:
            slot = self._slot

        if slot is None or slot.frame_id == since:
            return None

        return slot

    def close(self):
        """Stop capture and release the device.

        The refcount, thread/stop-token references, and status are all reset
        in one critical section: from the engine's point of view a session
        ends the moment this method has taken the lock, regardless of how
        long the underlying thread takes to actually unwind. That keeps a
        slow-to-exit thread from leaving the engine permanently bricked (a
        later acquire() always sees refcount 0 and starts a genuinely new
        session) and keeps this method from clobbering that new session's
        status if it happens to still be joining the old thread when the new
        one reaches STREAMING.
        """
        with self._lock:
            stop_event = self._stop_event
            thread = self._thread
            self._thread = None
            self._stop_event = None
            self._refcount = 0
            self._status = DepthStatus.IDLE
            self._status_reason = "not started"

        if stop_event is not None:
            stop_event.set()

        if thread is not None:
            thread.join(timeout=JOIN_TIMEOUT_S)
            # A thread that is still blocked past the timeout (e.g. stuck in
            # source.read()) is left to exit on its own, daemonised, and will
            # close its own source when it eventually notices its stop_event.
            # Its identity was already detached from self._thread/_stop_event
            # above, so it cannot be mistaken for -- or clobber the status of
            # -- whatever session a later acquire() has since started.

    def _start(self):
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._run, args=(stop_event,), name="depth-capture", daemon=True
        )
        with self._lock:
            self._stop_event = stop_event
            self._thread = thread
            self._status = DepthStatus.CONNECTING
            self._status_reason = "opening device"

        thread.start()

    def _set_status_if_current(self, stop_event, status, reason):
        """Apply a status transition only if `stop_event` is still live.

        Guards against a thread that has already been told to stop (or that a
        newer _start() has already superseded) clobbering the status of
        whatever session is current by the time it gets around to running.
        """
        with self._lock:
            if self._stop_event is stop_event:
                self._status = status
                self._status_reason = reason

    def _publish(self, data, width, height, depth_scale):
        with self._lock:
            self._frame_id += 1
            self._slot = Frame(self._frame_id, data, width, height, depth_scale)

    def _run(self, stop_event):
        source = None
        width = height = 0
        depth_scale = 1.0
        backoff = INITIAL_BACKOFF_S

        try:
            while not stop_event.is_set():
                if source is None:
                    self._set_status_if_current(
                        stop_event, DepthStatus.CONNECTING, "opening device"
                    )
                    try:
                        source = self._source_factory()
                        width, height, depth_scale = source.open()
                    except Exception as error:
                        # Any failure is a disconnect: no device, no SDK, no
                        # permission. Report it and try again later, never crash.
                        source = self._safe_close(source)
                        self._set_status_if_current(
                            stop_event, DepthStatus.UNAVAILABLE, str(error)
                        )
                        self._sleep_fn(backoff)
                        backoff = min(backoff * 2, MAX_BACKOFF_S)
                        continue

                    self._set_status_if_current(
                        stop_event,
                        DepthStatus.STREAMING,
                        "%dx%d depth stream" % (width, height),
                    )

                try:
                    frame = source.read()
                except Exception as error:
                    # A handle that opened but then failed to read is still a
                    # disconnect (flaky cable, wedged device): throttle it the
                    # same way a failed open is throttled, so a device that
                    # opens fine but never yields a frame cannot spin hot.
                    source = self._safe_close(source)
                    self._set_status_if_current(
                        stop_event, DepthStatus.UNAVAILABLE, str(error)
                    )
                    self._sleep_fn(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF_S)
                    continue

                if frame is None:
                    continue  # timeout, not an error

                if stop_event.is_set():
                    break

                # Backoff means "time since the stream last actually produced
                # a frame", not "time since we last got a handle" -- reset it
                # here, not on a bare successful open.
                backoff = INITIAL_BACKOFF_S
                self._publish(frame, width, height, depth_scale)
        finally:
            self._safe_close(source)

    def _safe_close(self, source):
        """Close a source, swallowing errors. Returns None for reassignment."""
        if source is not None:
            try:
                source.close()
            except Exception:
                pass
        return None
