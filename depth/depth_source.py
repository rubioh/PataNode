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

from numeric_locale import restoreCNumericLocale


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

    Matches the Gemini 2's resolution (1280x800) so texture allocation and
    upload cost behave as they do with the real device. The 10fps default is
    deliberately slower than the camera's 30fps on a USB 3 link: development
    without hardware benefits from a rate that makes individual frames visible,
    and anything depending on the exact frame rate would be depending on the
    link speed anyway.

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

    # A frame arrives every ~33ms at the 30fps profile this selects, and every
    # 100ms at the slowest one it will fall back to. 200ms clears both with
    # headroom, so a timeout means something is actually wrong rather than
    # that the deadline sat on the frame period.
    READ_TIMEOUT_MS = 200

    # How long open() will wait for the first frame before giving up. The frame
    # is needed because only a frame knows the sensor's raw-units-to-mm scale.
    OPEN_TIMEOUT_S = 3.0

    # The only format this source can decode. read() reinterprets the frame
    # buffer as flat uint16 and reshapes it, which holds for Y16 alone: Y14 is
    # bit-packed and RLE is run-length compressed, so both carry a pixel count
    # that does not match the profile's dimensions.
    DEPTH_FORMAT = "Y16"

    # Tried in order, first advertised match wins. Full resolution is worth
    # more than frame rate here (depth feeds a texture, not a control loop),
    # so the resolution steps down only after every frame rate is exhausted.
    PREFERRED_PROFILES = (
        (1280, 800, 30),
        (1280, 800, 15),
        (1280, 800, 10),
        (640, 400, 30),
        (640, 400, 15),
    )

    # Applied in order to every frame. Decimation goes first so the four
    # costlier filters behind it work on a quarter of the pixels -- and, being
    # first, it is also what makes the delivered frame half the profile's
    # resolution. Resolved by name at open() rather than imported at module
    # scope, so a build missing one is reported as such instead of crashing.
    FILTER_NAMES = (
        "DecimationFilter",
        "ThresholdFilter",
        "NoiseRemovalFilter",
        "SpatialAdvancedFilter",
        "TemporalFilter",
    )

    def __init__(self):
        self._pipeline = None
        self._width = 0
        self._height = 0
        self._chain = []
        # Recorded for diagnostics: which profile actually got selected is the
        # first thing worth knowing when frames look wrong.
        self.profile_format = None
        self.profile_fps = 0

    def open(self):
        try:
            from pyorbbecsdk import Config, OBFormat, OBSensorType, Pipeline
        except ImportError as error:
            raise DepthSourceError(
                "pyorbbecsdk is not installed: %s" % error
            ) from error

        # main.py pins this at startup, but LC_NUMERIC is process-global and
        # anything that calls setlocale can undo it later -- notably GTK
        # initialising when Qt opens a native file dialog. The SDK parses its
        # own config with locale-dependent C float parsing, so a comma decimal
        # separator makes it read "1.0" as 1 and refuse to open the camera.
        # Re-pinning here costs nothing and makes reconnects independent of
        # whatever the rest of the process did in the meantime.
        restoreCNumericLocale()

        try:
            pipeline = Pipeline()
            profiles = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
        except Exception as error:
            raise DepthSourceError(
                "could not list the depth stream profiles: %s" % error
            ) from error

        # Deliberately not get_default_video_stream_profile(): the default's
        # format varies with link speed and firmware, and on a USB 3 link this
        # device defaults to RLE, which read() cannot decode.
        profile = self._select_profile(profiles, getattr(OBFormat, self.DEPTH_FORMAT))

        try:
            config = Config()
            config.enable_stream(profile)
            pipeline.start(config)
        except Exception as error:
            raise DepthSourceError(
                "could not start the depth pipeline: %s" % error
            ) from error

        self._pipeline = pipeline
        self.profile_format = self.DEPTH_FORMAT
        self.profile_fps = profile.get_fps()

        # Provisional. The chain changes the frame's dimensions, so the numbers
        # this method returns have to come from a frame that has been through
        # it, not from the profile -- DepthEngine publishes them and DepthInput
        # sizes its texture from them.
        self._width = profile.get_width()
        self._height = profile.get_height()

        # Rebuilt on every open() rather than in __init__: TemporalFilter and
        # friends carry per-pixel state, and a reconnect must not blend the new
        # stream against what the previous session left behind.
        self._chain = self._buildChain()

        depth_scale = self._readFirstProcessedFrame()
        return self._width, self._height, depth_scale

    def _buildChain(self):
        """Instantiate the preprocessing filters.

        Resolved by getattr and reported separately from the Pipeline import on
        purpose: a build that lacks one of these classes is an SDK that *is*
        installed but is the wrong version, and "not installed" would send you
        looking in entirely the wrong place. The message names the one missing.
        """
        import pyorbbecsdk

        chain = []

        for name in self.FILTER_NAMES:
            factory = getattr(pyorbbecsdk, name, None)
            if factory is None:
                raise DepthSourceError(
                    "this pyorbbecsdk build has no %s -- the preprocessing "
                    "chain needs %s" % (name, ", ".join(self.FILTER_NAMES))
                )
            chain.append(factory())

        return chain

    def _process(self, depth_frame):
        """Run the chain. None means the chain swallowed the frame."""
        for depth_filter in self._chain:
            depth_frame = depth_filter.process(depth_frame)
            # A filter is allowed to hold a frame back while it warms up --
            # TemporalFilter does. That is a timeout, not an error, and read()
            # already reports None as "nothing arrived this tick".
            if depth_frame is None:
                return None

        return depth_frame

    def _select_profile(self, profiles, wanted_format):
        """Pick the best profile this source can actually decode.

        Filtering by format first is the point: a profile in any other format
        would start streaming happily and then fail on every read().
        """
        candidates = []
        advertised = []

        for index in range(profiles.get_count()):
            profile = profiles[index]
            profile_format = profile.get_format()
            advertised.append(str(profile_format))
            if profile_format == wanted_format:
                candidates.append(profile)

        if not candidates:
            raise DepthSourceError(
                "the camera advertises no %s depth profile (offered: %s)"
                % (self.DEPTH_FORMAT, ", ".join(sorted(set(advertised))) or "nothing")
            )

        for width, height, fps in self.PREFERRED_PROFILES:
            for profile in candidates:
                if (
                    profile.get_width() == width
                    and profile.get_height() == height
                    and profile.get_fps() == fps
                ):
                    return profile

        # No preference matched, so this is a device the list never anticipated.
        # Streaming at an unplanned resolution beats reporting no camera.
        return max(
            candidates,
            key=lambda p: (p.get_width() * p.get_height(), p.get_fps()),
        )

    def _readFirstProcessedFrame(self):
        """Pull frames until one survives the chain, and return its depth scale.

        Only a frame carries the raw-units-to-millimetres factor, so open() has
        to see one. Succeeding here also means open() genuinely implies
        "streaming" rather than merely "device found".

        It also settles the delivered resolution: the chain decimates, so the
        profile's dimensions are not what read() will hand back. Taking them
        from a processed frame is what keeps read()'s size check honest.
        """
        deadline = time.monotonic() + self.OPEN_TIMEOUT_S

        while time.monotonic() < deadline:
            # Wrapped so open() honours the module contract and raises only
            # DepthSourceError: an SDK exception escaping raw would reach the
            # engine as an opaque string with no indication of what failed.
            try:
                frames = self._pipeline.wait_for_frames(self.READ_TIMEOUT_MS)
            except Exception as error:
                self.close()
                raise DepthSourceError(
                    "the device stopped responding while opening: %s" % error
                ) from error

            if frames is None:
                continue
            depth_frame = frames.get_depth_frame()
            if depth_frame is None:
                continue

            # Read the scale off the raw frame: it is a property of the sensor,
            # and the filters have no reason to preserve it.
            depth_scale = depth_frame.get_depth_scale()

            depth_frame = self._process(depth_frame)
            if depth_frame is None:
                continue

            self._width = depth_frame.get_width()
            self._height = depth_frame.get_height()
            return depth_scale

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

        depth_frame = self._process(depth_frame)
        if depth_frame is None:
            return None

        # np.frombuffer gives a read-only view onto memory the SDK will reuse.
        # Copy so the engine can publish it and the main thread can read it
        # long after this iteration.
        data = np.frombuffer(depth_frame.get_data(), dtype=np.uint16)

        # Checked against the dimensions open() measured downstream of the
        # chain, not against the profile's: decimation makes those two differ
        # by design. A mismatch here means the chain changed its output size
        # mid-stream, or the stream is not really the format we asked for.
        # Reshaping would raise a bare ValueError about array shapes; the
        # engine catches that and reports it verbatim, which explains nothing.
        expected = self._width * self._height
        if data.size != expected:
            raise DepthSourceError(
                "expected %d pixels for %dx%d after the filter chain but the "
                "frame carried %d -- the stream is probably not %s"
                % (expected, self._width, self._height, data.size, self.DEPTH_FORMAT)
            )

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
    """Map a --depth-source argument to a zero-argument source factory.

    'orbbec' means the camera, which now runs in a child process: its filter
    chain holds the GIL for about 68% of the 14.5 ms it spends on each frame,
    and at 31 fps that stalls the render loop for roughly 306 ms a second.
    There is deliberately no in-process option -- two ways to run the camera
    would mean two behaviours to reason about, and this is the one that works.
    """
    if kind == "synthetic":
        return SyntheticSource

    from depth.depth_process import ProcessSource

    return ProcessSource
