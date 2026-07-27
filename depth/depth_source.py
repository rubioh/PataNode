"""Frame sources for the depth camera.

A DepthSource knows how to talk to one kind of depth device. It knows nothing
about threads (DepthEngine owns those) or OpenGL (DepthInput owns that).
Keeping the SDK behind this interface is what lets the whole pipeline be
developed and verified with no camera attached -- see SyntheticSource.

Contract:
    open()  -> (width, height, depth_scale). Raises DepthSourceError on failure.
    read()  -> (height, width) uint16 array, or None if no frame arrived within
               the source's timeout. None is normal, not an error.
    close() -> release the device. Must tolerate being called twice.
"""

import time

import numpy as np


class DepthSourceError(Exception):
    """A source could not open, or lost its device."""


class DepthSource:
    def open(self):
        raise NotImplementedError

    def read(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class SyntheticSource(DepthSource):
    """A fake depth camera: a distance ramp with a moving near blob and a hole.

    Defaults deliberately match the Gemini 2's working profile (1280x800 at
    10fps) so that timing behaviour during development matches the real device.

    sleep_fn is injectable purely so tests can run without real-time pacing.
    """

    def __init__(self, width=1280, height=800, fps=10, sleep_fn=time.sleep):
        self._width = width
        self._height = height
        self._fps = fps
        self._sleep_fn = sleep_fn
        self._opened = False
        self._frame_index = 0
        self._ramp = None

    def open(self):
        # Ramp spans the node's default near/far (500..4000mm) so the synthetic
        # image covers the full 0..1 output range without touching parameters.
        columns = np.linspace(500, 4000, self._width, dtype=np.float32)
        self._ramp = np.tile(columns, (self._height, 1)).astype(np.uint16)
        self._frame_index = 0
        self._opened = True
        return self._width, self._height, 1.0

    def read(self):
        if not self._opened:
            raise DepthSourceError("read() on a SyntheticSource that is not open")

        self._sleep_fn(1.0 / self._fps)
        frame = self._ramp.copy()

        # A near disc sweeping horizontally: something that visibly moves.
        centre_x = int((self._frame_index * 13) % self._width)
        centre_y = self._height // 2
        radius = self._height // 6
        rows, columns = np.ogrid[: self._height, : self._width]
        disc = (columns - centre_x) ** 2 + (rows - centre_y) ** 2 <= radius**2
        frame[disc] = 800

        # A static block of unmeasured pixels, so the alpha path is exercised.
        frame[: self._height // 10, : self._width // 10] = 0

        self._frame_index += 1
        return frame

    def close(self):
        self._opened = False
