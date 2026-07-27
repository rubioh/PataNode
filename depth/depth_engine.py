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
        self._running = False

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
        self._running = False
        thread = self._thread
        self._thread = None

        if thread is not None:
            thread.join(timeout=JOIN_TIMEOUT_S)

        self._set_status(DepthStatus.IDLE, "not started")

    def _start(self):
        self._running = True
        self._set_status(DepthStatus.CONNECTING, "opening device")
        self._thread = threading.Thread(
            target=self._run, name="depth-capture", daemon=True
        )
        self._thread.start()

    def _set_status(self, status, reason):
        with self._lock:
            self._status = status
            self._status_reason = reason

    def _publish(self, data, width, height, depth_scale):
        with self._lock:
            self._frame_id += 1
            self._slot = Frame(self._frame_id, data, width, height, depth_scale)

    def _run(self):
        source = self._source_factory()
        width, height, depth_scale = source.open()
        self._set_status(DepthStatus.STREAMING, "%dx%d depth stream" % (width, height))

        while self._running:
            frame = source.read()
            if frame is None:
                continue
            self._publish(frame, width, height, depth_scale)

        source.close()
