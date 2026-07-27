# Depth Camera Input Node Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the Orbbec Gemini 2 depth stream inside the PataNode graph as a texture node that shaders can sample.

**Architecture:** Three layers with one responsibility each. `DepthSource` talks to the SDK and nothing else. `DepthEngine` owns a background capture thread and publishes the newest frame into a single latest-wins slot. `DepthInput`/`DepthInputNode` upload that frame as a `GL_R16UI` texture and normalise it to 0..1 in GLSL. The layers depend downward only, so `depth/` imports neither Qt nor moderngl.

**Tech Stack:** Python 3.11.5, moderngl 5.12, PyQt5, numpy, pytest (added by this plan), `pyorbbecsdk` (optional, manually installed wheel).

**Spec:** `docs/superpowers/specs/2026-07-27-depth-camera-input-node-design.md`

## Global Constraints

- **Python 3.11.5.** Run everything with `.venv/bin/python`, never `uv run` — `uv run` uses uv's managed interpreter, not this project's `.venv`.
- **`.venv` is a symlink** to the main checkout's environment. Anything installed here is installed there too.
- **Import order is load-bearing.** `program.program_conf` MUST be imported before `node.node_conf`, or the circular import fixed in `51fde83` returns. `main.py` does this deliberately. Any smoke check must follow the same order.
- **`depth/` must not import `node`, `program`, `gui`, or PyQt5** at any scope. That decoupling is what makes it testable without a display, and what prevents new import cycles.
- **`pyorbbecsdk` must never be imported at module scope.** It is an optional, manually installed dependency; a module-scope import turns its absence into an app-wide startup crash.
- **Opcode is 1029** (`name_to_opcode("DepthInput")`), verified free in `SHADER_NODES`, `AUDIO_NODES`, and `SHADER_PROGRAMS`.
- **Depth profile on this hardware:** 1280×800 @ 10 fps. Frame period 100 ms.
- **isort, black, and autoflake** run via pre-commit on commit — not ruff, despite ruff being the declared dev dependency. Let them reformat; re-stage and commit again if they do.
- **Never use bare `git stash`** — the stash stack is shared across worktrees.

## File Structure

| File | Responsibility |
| --- | --- |
| `depth/__init__.py` | Empty. Keeps `depth` a package without pulling in submodules. |
| `depth/depth_source.py` | `DepthSourceError`, `DepthSource` interface, `SyntheticSource`, `OrbbecSource`, `make_source_factory`. The only file that touches the SDK. |
| `depth/depth_engine.py` | `DepthStatus`, `Frame`, `DepthEngine`. Thread, refcount, reconnect, frame slot. |
| `program/input/depth_input/__init__.py` | Package marker + re-export for registration. |
| `program/input/depth_input/depth_input.py` | `DepthInput(ProgramBase)` + `DepthInputNode(ShaderNode, Texture)`. |
| `program/input/depth_input/depth_input.glsl` | Normalisation shader. Integer sampler. |
| `tests/depth/test_depth_source.py` | Source behaviour, no hardware. |
| `tests/depth/test_depth_engine.py` | Lifecycle, slot semantics, reconnect. |
| `tests/depth/test_depth_shader.py` | Headless moderngl check of the `u2` → `usampler2D` path. |
| `program/program_conf.py` (modify) | Add `import program.input` to the registration import block. |
| `program/input/__init__.py` (modify) | Import the depth node so it registers. |
| `main.py` (modify) | `--depth-source` argument. |
| `app.py` (modify) | Construct `DepthEngine`, close it on exit. |
| `README.md` (modify) | Optional depth camera install instructions. |

---

### Task 1: Test scaffolding and `SyntheticSource`

Establishes the source interface and the fake camera everything else is developed against. Nothing here needs hardware.

**Files:**
- Create: `depth/__init__.py`
- Create: `depth/depth_source.py`
- Create: `tests/__init__.py`, `tests/depth/__init__.py`
- Create: `tests/depth/test_depth_source.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing.
- Produces: `DepthSourceError(Exception)`; `DepthSource` with `open() -> tuple[int, int, float]`, `read() -> np.ndarray | None`, `close() -> None`; `SyntheticSource(width=1280, height=800, fps=10, sleep_fn=time.sleep)`.

The `sleep_fn` parameter exists so tests can run the source at full speed without waiting on real frame pacing. Do not remove it.

- [ ] **Step 1: Add pytest and configure it**

In `pyproject.toml`, extend the existing `[dependency-groups]` dev list and add a pytest section:

```toml
[dependency-groups]
dev = [
    "ruff>=0.12.0",
    "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Then install it:

```bash
.venv/bin/python -m pip install "pytest>=8.0"
```

- [ ] **Step 2: Create the package directories**

```bash
mkdir -p depth tests/depth
touch depth/__init__.py tests/__init__.py tests/depth/__init__.py
```

`depth/__init__.py` stays empty — importing submodules from it would drag the SDK wrapper into every import of `depth`.

- [ ] **Step 3: Write the failing tests**

Create `tests/depth/test_depth_source.py`:

```python
import numpy as np
import pytest

from depth.depth_source import DepthSourceError, SyntheticSource


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
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_source.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'depth.depth_source'`

- [ ] **Step 5: Write the implementation**

Create `depth/depth_source.py`:

```python
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
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_source.py -v`
Expected: PASS, 7 passed

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml depth/ tests/
git commit -m "feat(depth): add DepthSource interface and SyntheticSource"
```

---

### Task 2: `DepthEngine` — capture thread, frame slot, refcount

The happy path only. Reconnect and failure handling arrive in Task 3.

**Files:**
- Create: `depth/depth_engine.py`
- Create: `tests/depth/test_depth_engine.py`

**Interfaces:**
- Consumes: `DepthSource` contract from Task 1.
- Produces: `DepthStatus` enum (`IDLE`, `CONNECTING`, `STREAMING`, `UNAVAILABLE`); `Frame = namedtuple("Frame", "frame_id data width height depth_scale")`; `NO_FRAME_ID = 0`; `DepthEngine(source_factory, sleep_fn=time.sleep)` with `.status`, `.status_reason`, `.acquire()`, `.release()`, `.get_frame(since=NO_FRAME_ID) -> Frame | None`, `.close()`.

`frame_id` starts at 0 meaning "no frame yet" and increments per published frame. Consumers store the last id they saw and pass it as `since`.

- [ ] **Step 1: Write the failing tests**

Create `tests/depth/test_depth_engine.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'depth.depth_engine'`

- [ ] **Step 3: Write the implementation**

Create `depth/depth_engine.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_engine.py -v`
Expected: PASS, 10 passed

- [ ] **Step 5: Commit**

```bash
git add depth/depth_engine.py tests/depth/test_depth_engine.py
git commit -m "feat(depth): add DepthEngine with latest-wins frame slot and refcount"
```

---

### Task 3: `DepthEngine` — reconnect, backoff, status reporting

Turns `_run` into the state machine that survives a missing or unplugged camera. This is the task that makes "open a saved scene on a laptop with no camera" work.

**Files:**
- Modify: `depth/depth_engine.py` (replace `_run`, add `_safe_close`, add backoff constants)
- Modify: `tests/depth/test_depth_engine.py` (append)

**Interfaces:**
- Consumes: everything from Task 2.
- Produces: `INITIAL_BACKOFF_S = 1.0`, `MAX_BACKOFF_S = 5.0`. Public API is unchanged — `status` now reports `UNAVAILABLE` with a human-readable `status_reason`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/depth/test_depth_engine.py`:

```python
from depth.depth_engine import INITIAL_BACKOFF_S, MAX_BACKOFF_S
from depth.depth_source import DepthSourceError


class FailingSource(FakeSource):
    """Fails to open until `fail_opens` attempts have been made."""

    def __init__(self, fail_opens=1, **kwargs):
        super().__init__(**kwargs)
        self.fail_opens = fail_opens
        self.attempts = 0

    def open(self):
        self.attempts += 1
        if self.attempts <= self.fail_opens:
            raise DepthSourceError("device not found")
        return super().open()


class DyingSource(FakeSource):
    """Streams a few frames, then loses the device on every later read."""

    def __init__(self, frames_before_death=3, **kwargs):
        super().__init__(**kwargs)
        self.frames_before_death = frames_before_death

    def read(self):
        if self._counter >= self.frames_before_death:
            raise DepthSourceError("device disconnected")
        return super().read()


def recording_sleep(delays):
    def sleep(seconds):
        delays.append(seconds)
        time.sleep(0.001)  # keep the reconnect loop from spinning hot

    return sleep


def test_failure_to_open_reports_unavailable_with_a_reason():
    source = FailingSource(fail_opens=99)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep([]))
    try:
        engine.acquire()

        assert wait_until(lambda: engine.status is DepthStatus.UNAVAILABLE)
        assert "device not found" in engine.status_reason
    finally:
        engine.close()


def test_a_missing_sdk_is_reported_not_raised():
    def factory():
        raise ImportError("No module named 'pyorbbecsdk'")

    engine = DepthEngine(factory, sleep_fn=recording_sleep([]))
    try:
        engine.acquire()

        assert wait_until(lambda: engine.status is DepthStatus.UNAVAILABLE)
        assert "pyorbbecsdk" in engine.status_reason
    finally:
        engine.close()


def test_open_failures_back_off_exponentially_up_to_the_cap():
    delays = []
    source = FailingSource(fail_opens=99)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep(delays))
    try:
        engine.acquire()

        assert wait_until(lambda: len(delays) >= 6)
    finally:
        engine.close()

    assert delays[0] == INITIAL_BACKOFF_S
    assert delays[1] == INITIAL_BACKOFF_S * 2
    assert delays[2] == INITIAL_BACKOFF_S * 4
    assert all(delay <= MAX_BACKOFF_S for delay in delays)
    assert delays[-1] == MAX_BACKOFF_S


def test_the_engine_recovers_when_the_device_appears():
    source = FailingSource(fail_opens=2)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep([]))
    try:
        engine.acquire()

        assert wait_until(lambda: engine.status is DepthStatus.STREAMING)
        assert wait_until(lambda: engine.get_frame() is not None)
    finally:
        engine.close()


def test_backoff_resets_after_a_successful_open():
    delays = []
    source = FailingSource(fail_opens=2)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep(delays))
    try:
        engine.acquire()
        assert wait_until(lambda: engine.status is DepthStatus.STREAMING)
    finally:
        engine.close()

    # Two failures: 1s then 2s. Nothing longer, because the third open worked.
    assert delays == [INITIAL_BACKOFF_S, INITIAL_BACKOFF_S * 2]


def test_a_read_error_closes_the_device_and_reconnects():
    source = DyingSource(frames_before_death=3)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep([]))
    try:
        engine.acquire()

        assert wait_until(lambda: source.close_count >= 1)
        assert wait_until(lambda: source.open_count >= 2)
    finally:
        engine.close()


def test_an_unplugged_camera_leaves_the_last_frame_readable():
    # The node keeps rendering the last good frame rather than going black the
    # instant the cable is pulled.
    source = DyingSource(frames_before_death=3)
    engine = DepthEngine(lambda: source, sleep_fn=recording_sleep([]))
    try:
        engine.acquire()
        assert wait_until(lambda: engine.get_frame() is not None)

        assert wait_until(lambda: source.close_count >= 1)

        assert engine.get_frame() is not None
    finally:
        engine.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_engine.py -v`
Expected: FAIL — `ImportError: cannot import name 'INITIAL_BACKOFF_S'`

- [ ] **Step 3: Add the backoff constants**

In `depth/depth_engine.py`, below `JOIN_TIMEOUT_S`:

```python
INITIAL_BACKOFF_S = 1.0
MAX_BACKOFF_S = 5.0
```

- [ ] **Step 4: Replace `_run` with the reconnecting state machine**

Task 2's review replaced the instance-wide `self._running` flag with a
per-thread `threading.Event` stop token, so `_run` already takes `stop_event`
and reports status through `_set_status_if_current`. Keep both — they are what
stop a superseded thread from resurrecting and from clobbering a newer
session's status. Do NOT reintroduce `self._running` or call `_set_status`
directly from `_run`.

Replace the whole `_run` method from Task 2 and add `_safe_close`:

```python
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

                    backoff = INITIAL_BACKOFF_S
                    self._set_status_if_current(
                        stop_event,
                        DepthStatus.STREAMING,
                        "%dx%d depth stream" % (width, height),
                    )

                try:
                    frame = source.read()
                except Exception as error:
                    source = self._safe_close(source)
                    self._set_status_if_current(
                        stop_event, DepthStatus.UNAVAILABLE, str(error)
                    )
                    continue

                if frame is None:
                    continue  # timeout, not an error

                if stop_event.is_set():
                    break

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
```

Three properties to preserve:

- The last published frame is deliberately left in the slot on disconnect, so
  consumers keep rendering it rather than going black the instant a cable is
  pulled.
- `_safe_close` runs in a `finally`, so a stopped or superseded thread always
  releases its device.
- The backoff sleep goes through `self._sleep_fn`, which the tests replace to
  avoid real waiting. It is not interruptible, so a `close()` during a backoff
  waits out at most one period (5 s worst case). That bound is accepted here;
  it is the same class as the deferred `JOIN_TIMEOUT_S` blocking noted in Task
  2's review.

- [ ] **Step 5: Run the whole depth suite to verify it passes**

Run: `.venv/bin/python -m pytest tests/depth/ -v`
Expected: PASS, 24 passed

- [ ] **Step 6: Commit**

```bash
git add depth/depth_engine.py tests/depth/test_depth_engine.py
git commit -m "feat(depth): reconnect with exponential backoff and status reporting"
```

---

### Task 4: `OrbbecSource` and install documentation

The real camera. The SDK import lives inside `open()`, and a fake module in the tests exercises the wrapper without hardware.

**Files:**
- Modify: `depth/depth_source.py` (append `OrbbecSource`, `make_source_factory`)
- Modify: `tests/depth/test_depth_source.py` (append)
- Modify: `README.md`

**Interfaces:**
- Consumes: `DepthSource`, `DepthSourceError` from Task 1.
- Produces: `OrbbecSource()` implementing the `DepthSource` contract; `make_source_factory(kind: str) -> callable` where `kind` is `"orbbec"` or `"synthetic"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/depth/test_depth_source.py`:

```python
import sys
import types

from depth.depth_source import OrbbecSource, SyntheticSource, make_source_factory


class FakeDepthFrame:
    def __init__(self, width, height, scale, fill):
        self._width = width
        self._height = height
        self._scale = scale
        self._fill = fill

    def get_depth_scale(self):
        return self._scale

    def get_data(self):
        return np.full((self._height, self._width), self._fill, dtype=np.uint16).tobytes()


class FakeFrames:
    def __init__(self, depth_frame):
        self._depth_frame = depth_frame

    def get_depth_frame(self):
        return self._depth_frame


def install_fake_sdk(monkeypatch, width=1280, height=800, scale=1.0):
    """Install a minimal stand-in for pyorbbecsdk into sys.modules."""
    module = types.ModuleType("pyorbbecsdk")

    class FakeProfile:
        def get_width(self):
            return width

        def get_height(self):
            return height

    class FakeProfileList:
        def get_default_video_stream_profile(self):
            return FakeProfile()

    class FakePipeline:
        started = False

        def get_stream_profile_list(self, _sensor_type):
            return FakeProfileList()

        def start(self, _config):
            FakePipeline.started = True

        def stop(self):
            FakePipeline.started = False

        def wait_for_frames(self, _timeout_ms):
            return FakeFrames(FakeDepthFrame(width, height, scale, 1234))

    module.Pipeline = FakePipeline
    module.Config = lambda: types.SimpleNamespace(enable_stream=lambda _profile: None)
    module.OBSensorType = types.SimpleNamespace(DEPTH_SENSOR=object())

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


def test_read_before_open_raises():
    with pytest.raises(DepthSourceError):
        OrbbecSource().read()


def test_factory_selects_the_synthetic_source():
    assert isinstance(make_source_factory("synthetic")(), SyntheticSource)


def test_factory_defaults_to_the_real_camera():
    assert isinstance(make_source_factory("orbbec")(), OrbbecSource)
    assert isinstance(make_source_factory("anything-else")(), OrbbecSource)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_source.py -v`
Expected: FAIL — `ImportError: cannot import name 'OrbbecSource'`

- [ ] **Step 3: Write the implementation**

Append to `depth/depth_source.py`:

```python
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
            raise DepthSourceError("pyorbbecsdk is not installed: %s" % error) from error

        try:
            pipeline = Pipeline()
            config = Config()
            profiles = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
            profile = profiles.get_default_video_stream_profile()
            config.enable_stream(profile)
            pipeline.start(config)
        except Exception as error:
            raise DepthSourceError("could not start the depth pipeline: %s" % error) from error

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
        raise DepthSourceError("no depth frame arrived within %ss" % self.OPEN_TIMEOUT_S)

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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/depth/ -v`
Expected: PASS, 31 passed

- [ ] **Step 5: Document the optional install**

Append to `README.md`:

```markdown
## Depth camera (optional)

The Depth Input node streams from an Orbbec Gemini 2. The camera is optional —
without it the node renders transparent black and the app runs normally.

`pyorbbecsdk` is **not** in `pyproject.toml`. It is not on PyPI, and building
from source is broken (the upstream git-LFS remote is missing objects). Install
the prebuilt wheel instead. For Python 3.11 on linux x86_64, download
`pyorbbecsdk2-2.1.1-cp311-cp311-linux_x86_64.whl` from
https://github.com/orbbec/pyorbbecsdk/releases and:

```bash
.venv/bin/python -m pip install pyorbbecsdk2-2.1.1-cp311-cp311-linux_x86_64.whl
sudo sh .venv/lib/python3.11/site-packages/pyorbbecsdk/shared/install_udev_rules.sh
```

The package is named `pyorbbecsdk2` but imports as `pyorbbecsdk`. Replug the
camera after installing the udev rules.

**The Gemini 2 must be on a USB 3.0 port.** On a 480M link it drops off the bus
mid-enumeration with `Input/Output Error`. Check with `lsusb -t` — the Orbbec
line must read 5000M or 10000M. A USB-2 or charge-only cable also forces 480M.

To develop without hardware, run with a fake camera:

```bash
.venv/bin/python main.py --depth-source synthetic
```
```

- [ ] **Step 6: Commit**

```bash
git add depth/depth_source.py tests/depth/test_depth_source.py README.md
git commit -m "feat(depth): add OrbbecSource and document the optional SDK install"
```

---

### Task 5: Application wiring

Gives the app a `depth_engine` for nodes to find, and a CLI switch for the fake camera.

**Files:**
- Modify: `main.py:18` (argument block)
- Modify: `app.py:33-51` (`PataShadeApp.__init__`) and add `closeEvent`
- Create: `tests/depth/test_app_wiring.py`

**Interfaces:**
- Consumes: `DepthEngine` (Task 2), `make_source_factory` (Task 4).
- Produces: `PataShadeApp.depth_engine`, a `DepthEngine` that is always present and starts idle. Nodes reach it as `scene.app.depth_engine`.

- [ ] **Step 1: Write the failing test**

Create `tests/depth/test_app_wiring.py`:

```python
"""Wiring checks that do not need a Qt display.

The full app cannot be constructed headlessly, so these assert on the argument
parser and the factory contract rather than on PataShadeApp itself.
"""

import subprocess
import sys

from depth.depth_engine import DepthEngine, DepthStatus
from depth.depth_source import OrbbecSource, SyntheticSource, make_source_factory


def test_main_exposes_a_depth_source_argument():
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert "--depth-source" in result.stdout
    assert "synthetic" in result.stdout


def test_an_engine_built_from_the_default_factory_stays_idle():
    # Constructing the engine must not open the camera; nothing should happen
    # until a node acquires it.
    engine = DepthEngine(make_source_factory("orbbec"))

    assert engine.status is DepthStatus.IDLE
    assert engine.get_frame() is None


def test_the_synthetic_factory_is_selected_by_name():
    assert isinstance(make_source_factory("synthetic")(), SyntheticSource)
    assert isinstance(make_source_factory("orbbec")(), OrbbecSource)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/depth/test_app_wiring.py -v`
Expected: FAIL on `test_main_exposes_a_depth_source_argument` — `--depth-source` is absent from the help output.

- [ ] **Step 3: Add the CLI argument**

In `main.py`, after the `--server` line:

```python
    parser.add_argument("--server", action="store_true")
    parser.add_argument(
        "--depth-source",
        choices=["orbbec", "synthetic"],
        default="orbbec",
        help="depth camera backend; 'synthetic' fakes a camera for development",
    )
```

- [ ] **Step 4: Construct the engine in the app**

In `app.py`, add to the imports at the top:

```python
from depth.depth_engine import DepthEngine
from depth.depth_source import make_source_factory
```

In `PataShadeApp.__init__`, beside the other engines (the `self.light_engine` line):

```python
        self.audio_engine = AudioEngine()
        self.light_engine = LightEngine(args)
        # Idle until a Depth Input node acquires it -- no USB traffic for users
        # who never touch depth.
        self.depth_engine = DepthEngine(
            make_source_factory(getattr(args, "depth_source", "orbbec"))
        )
```

`getattr` with a default keeps `main_light.py`, which builds its own args, working.

- [ ] **Step 5: Close the engine on exit**

Add to `PataShadeApp` in `app.py`:

```python
    def closeEvent(self, event):
        # Must come first: the base implementation calls sys.exit(0).
        self.depth_engine.close()
        super().closeEvent(event)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/depth/ -v`
Expected: PASS, 34 passed

- [ ] **Step 7: Verify the app still imports**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
import program.program_conf
import node.node_conf as nc
print('shader nodes:', len(nc.SHADER_NODES))
"
```

Expected: `shader nodes: 83` with no traceback. `program.program_conf` must be imported first — see Global Constraints.

- [ ] **Step 8: Commit**

```bash
git add main.py app.py tests/depth/test_app_wiring.py
git commit -m "feat(depth): wire DepthEngine into the app with a --depth-source flag"
```

---

### Task 6: The `DepthInput` node, shader, and registration

The GL layer. The headless shader test settles whether moderngl's `u2` maps to a `usampler2D`-compatible texture on this driver — the last open question from the spec.

**Files:**
- Create: `program/input/depth_input/__init__.py`
- Create: `program/input/depth_input/depth_input.glsl`
- Create: `program/input/depth_input/depth_input.py`
- Create: `tests/depth/test_depth_shader.py`
- Modify: `program/input/__init__.py`
- Modify: `program/program_conf.py:60` (registration import block)

**Interfaces:**
- Consumes: `DepthEngine.get_frame()` returning `Frame(frame_id, data, width, height, depth_scale)` (Task 2); `scene.app.depth_engine` (Task 5).
- Produces: `OP_CODE_DEPTH_INPUT = 1029`; `DepthInput(ProgramBase)`; `DepthInputNode(ShaderNode, Texture)` with no inputs and one output of type 3.

**Ordering inside `DepthInput.__init__` matters.** `initProgram` sets `self.name`, and `initUniformsBinding` writes into `cpu_adaptable_parameters_dict[self.name + "program"]`. Follow the order used in `program/scene/texture/texture.py`: `initParams`, `initProgram`, `initFBOSpecifications`, `initUniformsBinding`.

- [ ] **Step 1: Write the failing shader test**

Create `tests/depth/test_depth_shader.py`:

```python
"""Headless check of the depth normalisation shader.

This is the one GL behaviour worth automating: whether moderngl's dtype="u2"
produces a texture that a usampler2D can read. Everything else about the node
needs the running app.
"""

import os

import numpy as np
import pytest

moderngl = pytest.importorskip("moderngl")

SHADER_PATH = os.path.join("program", "input", "depth_input", "depth_input.glsl")
VERTEX_PATH = os.path.join("program", "base", "vertex_base.glsl")


@pytest.fixture
def ctx():
    try:
        context = moderngl.create_standalone_context()
    except Exception as error:
        pytest.skip("no standalone GL context available: %s" % error)
    yield context
    context.release()


def render_depth(ctx, depth_mm, near_mm=500.0, far_mm=4000.0, flip=(0.0, 0.0)):
    """Render a 1x1 depth image through the shader and return its RGBA pixel."""
    with open(VERTEX_PATH) as handle:
        vertex_source = handle.read()
    with open(SHADER_PATH) as handle:
        fragment_source = handle.read()

    program = ctx.program(
        vertex_shader=vertex_source, fragment_shader=fragment_source
    )

    texture = ctx.texture((1, 1), components=1, dtype="u2")
    texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
    texture.write(np.array([[depth_mm]], dtype=np.uint16))
    texture.use(0)

    program["depth_map"] = 0
    program["near_mm"] = near_mm
    program["far_mm"] = far_mm
    program["depth_scale"] = 1.0
    program["flip"] = flip
    program["iResolution"] = (1.0, 1.0)

    quad = ctx.buffer(
        np.array([-1, -1, 3, -1, -1, 3], dtype="f4").tobytes()
    )
    vao = ctx.vertex_array(program, [(quad, "2f", "in_position")])

    fbo = ctx.framebuffer([ctx.texture((1, 1), 4, dtype="f4")])
    fbo.use()
    fbo.clear(0.0, 0.0, 0.0, 0.0)
    vao.render(moderngl.TRIANGLES)

    return np.frombuffer(fbo.read(components=4, dtype="f4"), dtype="f4")


def test_a_measured_pixel_is_opaque(ctx):
    pixel = render_depth(ctx, depth_mm=2250)

    assert pixel[3] == pytest.approx(1.0)


def test_depth_is_normalised_between_near_and_far(ctx):
    pixel = render_depth(ctx, depth_mm=2250, near_mm=500.0, far_mm=4000.0)

    # 2250mm is the midpoint of 500..4000
    assert pixel[0] == pytest.approx(0.5, abs=1e-3)


def test_an_unmeasured_pixel_is_transparent(ctx):
    pixel = render_depth(ctx, depth_mm=0)

    assert pixel[3] == pytest.approx(0.0)


def test_depth_is_clamped_outside_the_near_far_window(ctx):
    assert render_depth(ctx, depth_mm=100)[0] == pytest.approx(0.0)
    assert render_depth(ctx, depth_mm=9000)[0] == pytest.approx(1.0)


def test_swapping_near_and_far_inverts_the_ramp(ctx):
    normal = render_depth(ctx, depth_mm=1000, near_mm=500.0, far_mm=4000.0)
    inverted = render_depth(ctx, depth_mm=1000, near_mm=4000.0, far_mm=500.0)

    assert inverted[0] == pytest.approx(1.0 - normal[0], abs=1e-3)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_shader.py -v`
Expected: FAIL — `FileNotFoundError` for `depth_input.glsl`. If instead every test SKIPS with "no standalone GL context available", that is acceptable on a headless machine; note it and rely on Task 7's manual verification for the shader.

- [ ] **Step 3: Write the shader**

Create `program/input/depth_input/depth_input.glsl`:

```glsl
#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;

// R16UI: an integer sampler, NEAREST filtering only. This is deliberate --
// linear filtering across a depth discontinuity interpolates foreground into
// background and invents surfaces that were never measured. Do not "fix" this
// to a sampler2D.
uniform usampler2D depth_map;

uniform float near_mm;
uniform float far_mm;
uniform float depth_scale;   // raw sensor units -> millimetres
uniform vec2 flip;           // 0 or 1 per axis

void main()
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;
    uv = mix(uv, 1.0 - uv, flip);

    uint raw = texture(depth_map, uv).r;

    // 0 means the sensor measured nothing here: a shadow, a dark or shiny
    // surface, out of range -- or no camera connected at all. Both cases are
    // reported the same way, as alpha 0.
    if (raw == 0u) {
        fragColor = vec4(0.0);
        return;
    }

    float mm = float(raw) * depth_scale;
    float d = clamp((mm - near_mm) / (far_mm - near_mm), 0.0, 1.0);

    fragColor = vec4(vec3(d), 1.0);
}
```

- [ ] **Step 4: Run the shader test to verify it passes**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_shader.py -v`
Expected: PASS, 5 passed (or 5 skipped if no GL context is available headlessly).

- [ ] **Step 5: Write the program and node**

Create `program/input/depth_input/depth_input.py`:

```python
from os.path import dirname, join

import moderngl
import numpy as np

from depth.depth_engine import NO_FRAME_ID
from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Texture
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, name_to_opcode, register_program


OP_CODE_DEPTH_INPUT = name_to_opcode("DepthInput")

DEFAULT_NEAR_MM = 500.0
DEFAULT_FAR_MM = 4000.0


@register_program(OP_CODE_DEPTH_INPUT)
class DepthInput(ProgramBase):
    """Uploads depth frames from the DepthEngine and normalises them in GLSL.

    Deliberately knows nothing about threads or the camera SDK: it pulls
    whatever the engine last published and blits it.
    """

    def __init__(
        self,
        ctx=None,
        major_version=3,
        minor_version=3,
        win_size=(960, 540),
        engine=None,
    ):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Depth Input"
        self.engine = engine

        self._last_frame_id = NO_FRAME_ID
        self._depth_scale = 1.0

        # Order matters: initProgram sets self.name, which initUniformsBinding
        # needs to key its parameter dict. Matches program/scene/texture.
        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

    def initParams(self):
        # A 1x1 zero texture so the shader always has something bindable, even
        # before the first frame -- or forever, if no camera ever appears. Raw 0
        # already means "unmeasured", so "no camera" and "hole" collapse into
        # the same transparent output instead of two cases downstream.
        self.depth_texture = self.ctx.texture((1, 1), components=1, dtype="u2")
        self.depth_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.depth_texture.write(np.zeros((1, 1), dtype=np.uint16))

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "depth_input.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [[self.win_size, 4, "f4"]]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initUniformsBinding(self):
        binding = {}
        self.add_float_cpu_adaptable_parameter("near_mm", DEFAULT_NEAR_MM)
        self.add_float_cpu_adaptable_parameter("far_mm", DEFAULT_FAR_MM)
        self.add_float_cpu_adaptable_parameter("flip_x", 0.0)
        self.add_float_cpu_adaptable_parameter("flip_y", 0.0)
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def _parameter(self, name, fallback):
        parameters = self.getCpuAdaptableParameters()["program"]
        try:
            return float(parameters[name]["eval_function"]["value"])
        except (KeyError, TypeError, ValueError):
            return fallback

    def updateParams(self, af=None):
        """Pull the newest frame from the engine, if there is one."""
        if self.engine is None:
            return

        frame = self.engine.get_frame(since=self._last_frame_id)
        if frame is None:
            return

        # A reconnect can come back on a different profile.
        if self.depth_texture.size != (frame.width, frame.height):
            self.depth_texture.release()
            self.depth_texture = self.ctx.texture(
                (frame.width, frame.height), components=1, dtype="u2"
            )
            self.depth_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)

        self.depth_texture.write(frame.data)
        self._depth_scale = frame.depth_scale
        self._last_frame_id = frame.frame_id

    def bindUniform(self, af=None):
        super().bindUniform(af)

        near_mm = self._parameter("near_mm", DEFAULT_NEAR_MM)
        far_mm = self._parameter("far_mm", DEFAULT_FAR_MM)

        # Equal near and far would divide by zero in the shader.
        if far_mm == near_mm:
            far_mm = near_mm + 1.0

        self.program["near_mm"] = near_mm
        self.program["far_mm"] = far_mm
        self.program["depth_scale"] = self._depth_scale
        self.program["flip"] = (
            1.0 if self._parameter("flip_x", 0.0) else 0.0,
            1.0 if self._parameter("flip_y", 0.0) else 0.0,
        )

    def norender(self):
        return self.fbos[0].color_attachments[0]

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.program["depth_map"] = 0
        self.depth_texture.use(0)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_DEPTH_INPUT)
class DepthInputNode(ShaderNode, Texture):
    op_title = "Depth Input"
    op_code = OP_CODE_DEPTH_INPUT
    content_label = ""
    content_label_objname = "depth_input"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])

        app = getattr(scene, "app", None)
        self.engine = getattr(app, "depth_engine", None)

        if self.engine is not None:
            self.engine.acquire()

        self.program = DepthInput(
            ctx=self.scene.ctx, win_size=(1920, 1080), engine=self.engine
        )
        self.eval()

    def remove(self):
        # Release before the node goes away, so the last node closing the graph
        # also closes the camera.
        if self.engine is not None:
            self.engine.release()
            self.engine = None

        super().remove()

    def render(self, audio_features=None):
        if self.engine is not None:
            self.grNode.setToolTip(self.engine.status_reason)

        if self.program is not None and self.program.already_called:
            return self.program.norender()

        return self.program.render(audio_features)
```

- [ ] **Step 6: Register the node**

Replace `program/input/__init__.py` with:

```python
from program.input.depth_input.depth_input import DepthInput
from program.input.std_input.std_input import StdInput

__all__ = ["DepthInput", "StdInput"]
```

Create `program/input/depth_input/__init__.py` as an empty file:

```bash
touch program/input/depth_input/__init__.py
```

In `program/program_conf.py`, add to the import block at the bottom of the file, immediately after `import program.output`:

```python
import program.output
import program.input
import program.scene
```

- [ ] **Step 7: Verify registration and the import order**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
import program.program_conf as pc
import node.node_conf as nc
print('shader nodes:', len(nc.SHADER_NODES))
print('DepthInput registered:', 1029 in nc.SHADER_NODES)
print('program registered   :', 1029 in pc.SHADER_PROGRAMS)
print('class:', nc.SHADER_NODES.get(1029))
"
```

Expected: `shader nodes: 85`, both registrations `True`, class `DepthInputNode`.

The count goes 83 → 85, not 84. `program.input` is not imported anywhere today, so `StdInputNode` (opcode 2) is currently unregistered and absent from the palette. Importing the package registers it alongside the depth node. This is expected and accepted — mention it in the commit message.

A traceback about a partially initialised `node.node_conf` means the new import broke the cycle order — move `import program.input` after `import program.output` and try again.

- [ ] **Step 8: Run the whole suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS, 39 passed (5 may skip without a GL context)

- [ ] **Step 9: Commit**

```bash
git add program/input/ program/program_conf.py tests/depth/test_depth_shader.py
git commit -m "feat(depth): add Depth Input node with GLSL depth normalisation"
```

---

### Task 7: Manual verification

Automated tests cover `depth/` and the shader in isolation. This task covers what only the running app can show. Work through the scenarios in order and record the result of each.

**Files:**
- Modify: `docs/superpowers/specs/2026-07-27-depth-camera-input-node-design.md` (record outcomes)

**Interfaces:**
- Consumes: everything.
- Produces: nothing. This is a verification gate.

- [ ] **Step 1: No camera, no SDK**

```bash
.venv/bin/python main.py
```

Add a Depth Input node from the Textures category. Confirm:
- The app does not crash and stays responsive.
- The node renders transparent black.
- Hovering the node shows a tooltip naming the problem (`pyorbbecsdk is not installed`, or a device error).
- Saving the scene and reopening it works.

- [ ] **Step 2: Synthetic camera**

```bash
.venv/bin/python main.py --depth-source synthetic
```

Add a Depth Input node and connect it to an output. Confirm:
- A horizontal ramp is visible with a disc sweeping across it.
- The top-left block is transparent (the hole).
- Raising `near_mm` toward 4000 visibly darkens the image.
- Setting `far_mm` below `near_mm` inverts it, near objects going bright.
- `flip_x` and `flip_y` set to 1 mirror the image on each axis.

- [ ] **Step 3: Real camera**

Install the SDK per the README, plug the Gemini 2 into a USB 3.0 port, then:

```bash
.venv/bin/python main.py
```

Confirm the stream appears, and that a hand held at a known distance lands where `near_mm` and `far_mm` predict.

Also confirm the **pixel format assumption**. `OrbbecSource.read()` assumes the default depth profile is 16-bit and reshapes with `dtype=np.uint16`. If the device's default profile is not 16-bit, `reshape` raises `ValueError` and the symptom is a permanent reconnect loop whose tooltip reads "cannot reshape array". Check the reported profile is 1280×800 and that frames arrive without that error. This cannot be verified without hardware — it is the one assumption in the SDK wrapper that no test can reach.

- [ ] **Step 4: Reconnect**

With the real camera streaming, unplug it. Confirm:
- The app stays responsive and the node keeps showing the last frame.
- The tooltip changes to a disconnect message.
- Replugging resumes streaming without restarting the app.

- [ ] **Step 5: Clean shutdown**

Close the app window normally (with and without a Depth Input node in the
graph). Confirm no traceback on exit and no lingering capture thread. Two lines
in `app.py` are reachable only this way and are covered by no automated test,
because `PataShadeApp` cannot be constructed headlessly: the
`getattr(args, "depth_source", "orbbec")` fallback and the `closeEvent`
override that closes the engine before the base class calls `sys.exit(0)`.

- [ ] **Step 6: Refcount**

Add a second Depth Input node. Confirm both render. Delete one; confirm the other keeps streaming. Delete both; confirm the camera LED turns off, or the log shows the capture thread stopping.

- [ ] **Step 6: Record the outcomes**

Add a "Verification results" section to the spec noting the date, which scenarios passed, and anything that did not. If a scenario failed, stop and fix it before continuing.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/specs/2026-07-27-depth-camera-input-node-design.md
git commit -m "docs: record depth camera verification results"
```

---

## Notes for the implementer

**Why `depth/` has no Qt.** It is the reason the engine can be tested at all. If you find yourself wanting a Qt signal in `depth/`, put the adapter in `app.py` instead.

**Why `sleep_fn` is injectable.** The reconnect tests would otherwise take 30+ seconds of real waiting. Do not inline `time.sleep`.

**Why frames are copied in `OrbbecSource.read()`.** `np.frombuffer` returns a view onto memory the SDK reuses on the next `wait_for_frames`. Without the copy, a published frame changes under the render thread.

**If a test hangs,** it is almost certainly `wait_until` waiting on a capture thread that never started. Check that `acquire()` was called and that the fixture's `engine.close()` runs in a `finally`.
