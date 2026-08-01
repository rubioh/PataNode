import sys
import types

import numpy as np
import pytest

from depth.depth_source import (
    DepthSourceError,
    OrbbecSource,
    SyntheticSource,
    make_source_factory,
)


def make_source(**kwargs):
    """A SyntheticSource that never actually sleeps."""
    kwargs.setdefault("sleep_fn", lambda _seconds: None)
    return SyntheticSource(**kwargs)


def test_open_reports_the_real_camera_profile():
    # Defaults match the Gemini 2's working profile so development timing
    # matches the hardware.
    assert make_source().open() == (1280, 800, 1.0)


def test_read_returns_a_uint16_frame_of_the_declared_shape():
    source = make_source()
    width, height, _scale = source.open()

    frame = source.read()

    assert frame.dtype == np.uint16
    assert frame.shape == (height, width)


def test_frame_contains_both_holes_and_measurements():
    # Zeros are unmeasured pixels. Without them the node's alpha path is
    # never exercised during development.
    source = make_source()
    source.open()

    frame = source.read()

    assert (frame == 0).any(), "expected a hole"
    assert (frame > 0).any(), "expected measured pixels"


def test_successive_frames_differ_so_motion_is_visible():
    source = make_source()
    source.open()

    first = source.read()
    for _ in range(5):
        later = source.read()

    assert not np.array_equal(first, later)


def test_read_paces_itself_at_the_declared_fps():
    delays = []
    source = SyntheticSource(fps=10, sleep_fn=delays.append)
    source.open()

    source.read()

    assert delays == [pytest.approx(0.1)]


def test_read_before_open_raises():
    with pytest.raises(DepthSourceError):
        make_source().read()


def test_read_after_close_raises():
    source = make_source()
    source.open()
    source.close()

    with pytest.raises(DepthSourceError):
        source.read()


class FakeDepthFrame:
    """A depth frame whose data is optionally backed by a shared buffer.

    When `buffer` is given, get_data() returns that same object on every
    call rather than allocating fresh bytes -- modelling the SDK reusing its
    own memory across wait_for_frames calls, which is exactly the hazard
    OrbbecSource.read()'s .copy() has to guard against.
    """

    def __init__(self, width, height, scale, fill=0, buffer=None):
        self._width = width
        self._height = height
        self._scale = scale
        self._fill = fill
        self._buffer = buffer

    def get_depth_scale(self):
        return self._scale

    def get_data(self):
        if self._buffer is not None:
            return self._buffer
        return np.full(
            (self._height, self._width), self._fill, dtype=np.uint16
        ).tobytes()


class FakeFrames:
    def __init__(self, depth_frame):
        self._depth_frame = depth_frame

    def get_depth_frame(self):
        return self._depth_frame


def install_fake_sdk(
    monkeypatch, width=1280, height=800, scale=1.0, fill=1234, profiles=None
):
    """Install a minimal stand-in for pyorbbecsdk into sys.modules.

    The returned module exposes `buffer`, the mutable bytearray backing depth
    frames, and `Pipeline.next_results`, a queue tests can push onto to make
    the *next* wait_for_frames call(s) return something other than a
    populated frame (None, or a FakeFrames whose get_depth_frame() is None).

    `profiles` is a list of (width, height, fps, format_name) tuples modelling
    what the device advertises; the first entry is what the SDK would hand back
    from get_default_video_stream_profile(). It defaults to a single Y16 entry
    matching `width`/`height`, so tests that do not care about format selection
    get a device that simply works.
    """
    module = types.ModuleType("pyorbbecsdk")
    buffer = bytearray(np.full((height, width), fill, dtype=np.uint16).tobytes())

    # Distinct sentinels: selection must compare formats by identity, exactly
    # as it does against the real SDK's enum members.
    formats = types.SimpleNamespace(Y16="Y16", Y14="Y14", RLE="RLE")

    if profiles is None:
        profiles = [(width, height, 30, "Y16")]

    class FakeProfile:
        def __init__(self, width, height, fps, format_name):
            self._width = width
            self._height = height
            self._fps = fps
            self._format = getattr(formats, format_name)

        def get_width(self):
            return self._width

        def get_height(self):
            return self._height

        def get_fps(self):
            return self._fps

        def get_format(self):
            return self._format

    class FakeProfileList:
        def __init__(self):
            self._profiles = [FakeProfile(*entry) for entry in profiles]

        def get_count(self):
            return len(self._profiles)

        def __getitem__(self, index):
            return self._profiles[index]

        def get_default_video_stream_profile(self):
            return self._profiles[0]

    class FakePipeline:
        started = False
        next_results = []

        def get_stream_profile_list(self, _sensor_type):
            return FakeProfileList()

        def start(self, _config):
            FakePipeline.started = True

        def stop(self):
            FakePipeline.started = False

        def wait_for_frames(self, _timeout_ms):
            if FakePipeline.next_results:
                return FakePipeline.next_results.pop(0)
            return FakeFrames(FakeDepthFrame(width, height, scale, buffer=buffer))

    module.Pipeline = FakePipeline
    module.Config = lambda: types.SimpleNamespace(enable_stream=lambda _profile: None)
    module.OBSensorType = types.SimpleNamespace(DEPTH_SENSOR=object())
    module.OBFormat = formats
    module.buffer = buffer

    monkeypatch.setitem(sys.modules, "pyorbbecsdk", module)
    return module


def test_a_missing_sdk_raises_depth_source_error_not_import_error(monkeypatch):
    # None in sys.modules makes `from pyorbbecsdk import ...` raise ImportError.
    monkeypatch.setitem(sys.modules, "pyorbbecsdk", None)

    with pytest.raises(DepthSourceError, match="pyorbbecsdk"):
        OrbbecSource().open()


def test_open_reports_the_profile_and_the_sensor_depth_scale(monkeypatch):
    install_fake_sdk(monkeypatch, width=1280, height=800, scale=0.25)

    assert OrbbecSource().open() == (1280, 800, 0.25)


def test_open_rejects_the_compressed_default_and_takes_y16(monkeypatch):
    # The regression. On a USB 3 link the Gemini 2 advertises RLE first, and
    # get_default_video_stream_profile() hands it over: run-length compressed,
    # so frames carry a variable byte count that read() cannot reshape.
    install_fake_sdk(
        monkeypatch,
        width=1280,
        height=800,
        profiles=[
            (1280, 800, 30, "RLE"),
            (1280, 800, 30, "Y14"),
            (1280, 800, 30, "Y16"),
        ],
    )

    source = OrbbecSource()
    source.open()

    assert source.profile_format == "Y16"


def test_open_falls_through_to_the_next_preferred_frame_rate(monkeypatch):
    install_fake_sdk(
        monkeypatch,
        width=1280,
        height=800,
        profiles=[
            (1280, 800, 30, "RLE"),
            (1280, 800, 15, "Y16"),
            (640, 400, 30, "Y16"),
        ],
    )

    # 1280x800@30 Y16 is not advertised, so the next preference entry wins --
    # full resolution matters more than frame rate.
    source = OrbbecSource()

    assert source.open()[:2] == (1280, 800)
    # Asserted explicitly: the RLE default shares this resolution, so checking
    # only the size would pass even if the format were still wrong.
    assert (source.profile_format, source.profile_fps) == ("Y16", 15)


def test_open_falls_back_to_the_largest_y16_when_no_preference_matches(monkeypatch):
    install_fake_sdk(
        monkeypatch,
        width=848,
        height=480,
        profiles=[
            (320, 240, 30, "Y16"),
            (848, 480, 25, "Y16"),
            (640, 480, 25, "Y16"),
        ],
    )

    # An unusual device should still stream rather than report unavailable.
    assert OrbbecSource().open()[:2] == (848, 480)


def test_open_raises_when_no_uncompressed_profile_exists(monkeypatch):
    install_fake_sdk(
        monkeypatch,
        profiles=[(1280, 800, 30, "RLE"), (1280, 800, 30, "Y14")],
    )

    # Naming what *was* advertised is the difference between a diagnosable
    # report and "unavailable" with no explanation.
    with pytest.raises(DepthSourceError, match="RLE"):
        OrbbecSource().open()


def test_read_rejects_a_frame_whose_size_contradicts_the_profile(monkeypatch):
    module = install_fake_sdk(monkeypatch, width=1280, height=800)
    source = OrbbecSource()
    source.open()

    # A frame carrying fewer pixels than the profile promises: the signature of
    # a compressed stream. It must surface as a DepthSourceError the engine can
    # report, not a bare ValueError about array shapes.
    module.Pipeline.next_results.append(
        FakeFrames(FakeDepthFrame(64, 1, 1.0, buffer=bytearray(128)))
    )

    with pytest.raises(DepthSourceError, match="1024000"):
        source.read()


def test_read_returns_a_reshaped_uint16_frame(monkeypatch):
    install_fake_sdk(monkeypatch, width=1280, height=800)
    source = OrbbecSource()
    source.open()

    frame = source.read()

    assert frame.dtype == np.uint16
    assert frame.shape == (800, 1280)
    assert (frame == 1234).all()


def test_read_owns_its_buffer_so_the_sdk_may_reuse_its_own(monkeypatch):
    install_fake_sdk(monkeypatch)
    source = OrbbecSource()
    source.open()

    frame = source.read()

    # np.frombuffer alone gives a read-only view onto SDK memory.
    assert frame.flags.owndata or frame.flags.writeable


def test_read_copy_survives_the_sdk_reusing_its_buffer(monkeypatch):
    # The behavioural version of the flags check above: model the SDK
    # actually reusing its own memory across wait_for_frames calls, and
    # confirm a previously-returned frame does not mutate underneath us.
    module = install_fake_sdk(monkeypatch, width=4, height=1, fill=1234)
    source = OrbbecSource()
    source.open()

    first = source.read()
    assert (first == 1234).all()

    # Simulate the SDK overwriting its internal buffer on the next frame.
    module.buffer[:] = np.full(4, 9999, dtype=np.uint16).tobytes()
    second = source.read()

    assert (
        first == 1234
    ).all(), "an earlier frame must not change underneath the caller"
    assert (second == 9999).all()


def test_read_returns_none_when_no_frames_arrive(monkeypatch):
    module = install_fake_sdk(monkeypatch)
    source = OrbbecSource()
    source.open()
    module.Pipeline.next_results.append(None)

    assert source.read() is None


def test_read_returns_none_when_the_frames_have_no_depth_frame(monkeypatch):
    module = install_fake_sdk(monkeypatch)
    source = OrbbecSource()
    source.open()
    module.Pipeline.next_results.append(FakeFrames(None))

    assert source.read() is None


def test_orbbec_read_before_open_raises():
    with pytest.raises(DepthSourceError):
        OrbbecSource().read()


def test_close_stops_the_pipeline(monkeypatch):
    module = install_fake_sdk(monkeypatch)
    source = OrbbecSource()
    source.open()
    assert module.Pipeline.started is True

    source.close()

    assert module.Pipeline.started is False


def test_close_is_safe_to_call_twice(monkeypatch):
    install_fake_sdk(monkeypatch)
    source = OrbbecSource()
    source.open()
    source.close()

    source.close()  # must not raise


def test_close_on_a_never_opened_source_is_safe():
    OrbbecSource().close()  # must not raise


def test_orbbec_read_after_close_raises(monkeypatch):
    install_fake_sdk(monkeypatch)
    source = OrbbecSource()
    source.open()
    source.close()

    with pytest.raises(DepthSourceError):
        source.read()


def test_factory_selects_the_synthetic_source():
    assert isinstance(make_source_factory("synthetic")(), SyntheticSource)


def test_factory_defaults_to_the_real_camera():
    assert isinstance(make_source_factory("orbbec")(), OrbbecSource)
    assert isinstance(make_source_factory("anything-else")(), OrbbecSource)
