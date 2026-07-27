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


class OrbbecSource(DepthSource):
    """Depth frames from an Orbbec camera via pyorbbecsdk.

    The SDK import happens inside open() on purpose. pyorbbecsdk ships as a
    manually installed wheel (see README) and is frequently absent; importing it
    at module scope would turn a missing optional dependency into a startup
    crash for the whole application.
    """

    # The working profile is 10fps, so a frame arrives every 100ms. The 100ms
    # used in TODO/gemini_sdk_test.py sits right on the frame period and times
    # out constantly.
    READ_TIMEOUT_MS = 200

    # How long open() will wait for the first frame before giving up. The frame
    # is needed because only a frame knows the sensor's raw-units-to-mm scale.
    OPEN_TIMEOUT_S = 3.0

    def __init__(self):
        self._pipeline = None
        self._width = 0
        self._height = 0

    def open(self):
        try:
            from pyorbbecsdk import Config, OBSensorType, Pipeline
        except ImportError as error:
            raise DepthSourceError(
                "pyorbbecsdk is not installed: %s" % error
            ) from error

        try:
            pipeline = Pipeline()
            config = Config()
            profiles = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
            profile = profiles.get_default_video_stream_profile()
            config.enable_stream(profile)
            pipeline.start(config)
        except Exception as error:
            raise DepthSourceError(
                "could not start the depth pipeline: %s" % error
            ) from error

        self._pipeline = pipeline
        self._width = profile.get_width()
        self._height = profile.get_height()

        depth_scale = self._read_depth_scale()
        return self._width, self._height, depth_scale

    def _read_depth_scale(self):
        """Pull frames until one reports its depth scale.

        Only a frame carries the raw-units-to-millimetres factor, so open() has
        to see one. Succeeding here also means open() genuinely implies
        "streaming" rather than merely "device found".
        """
        deadline = time.monotonic() + self.OPEN_TIMEOUT_S

        while time.monotonic() < deadline:
            frames = self._pipeline.wait_for_frames(self.READ_TIMEOUT_MS)
            if frames is None:
                continue
            depth_frame = frames.get_depth_frame()
            if depth_frame is None:
                continue
            return depth_frame.get_depth_scale()

        self.close()
        raise DepthSourceError(
            "no depth frame arrived within %ss" % self.OPEN_TIMEOUT_S
        )

    def read(self):
        if self._pipeline is None:
            raise DepthSourceError("read() on an OrbbecSource that is not open")

        frames = self._pipeline.wait_for_frames(self.READ_TIMEOUT_MS)
        if frames is None:
            return None

        depth_frame = frames.get_depth_frame()
        if depth_frame is None:
            return None

        # np.frombuffer gives a read-only view onto memory the SDK will reuse.
        # Copy so the engine can publish it and the main thread can read it
        # long after this iteration.
        data = np.frombuffer(depth_frame.get_data(), dtype=np.uint16)
        return data.reshape((self._height, self._width)).copy()

    def close(self):
        pipeline = self._pipeline
        self._pipeline = None

        if pipeline is not None:
            try:
                pipeline.stop()
            except Exception:
                pass


def make_source_factory(kind):
    """Map a --depth-source argument to a zero-argument source factory."""
    if kind == "synthetic":
        return SyntheticSource
    return OrbbecSource
