# Depth Capture Process Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Orbbec depth capture and its five-filter chain into a child process so their GIL cost stops stalling the render loop, and prove the gain with a before/after measurement against today's code.

**Architecture:** A new `ProcessSource` implements the existing three-method `DepthSource` interface (`open`/`read`/`close`) and is what `make_source_factory("orbbec")` returns. It spawns a child process that runs the *existing* `OrbbecSource` unchanged and publishes finished frames through a double-buffered `shared_memory` block with a sequence counter. Control messages (dimensions, errors, start/stop) travel over a `Pipe`. `DepthEngine`, `DepthInput` and `DepthStatus` are untouched; the engine's existing retry-with-backoff on `DepthSourceError` becomes the auto-restart mechanism for free.

**Tech Stack:** Python 3.11.5, `multiprocessing` (spawn context), `multiprocessing.shared_memory`, numpy <2.3, pyorbbecsdk, pytest.

Spec: `docs/superpowers/specs/2026-08-17-depth-capture-process-design.md`

## Global Constraints

- Python 3.11.5 exactly (`pyproject.toml` `requires-python`).
- numpy must stay `<2.3` — uniform binding breaks on 2.3+.
- Run everything with `.venv/bin/python`, never `uv run`.
- Launching the app requires `PATASHADE_INPUT_DEVICE=9`; the exported value of 12 does not exist and `AudioEngine.__init__` calls `exit(1)` without a valid capture device.
- `multiprocessing` must use the **spawn** context. Forking a process holding a GL context, Qt state and an open camera is out of scope and unsafe.
- `--depth-source` has exactly two values after this work: `orbbec` and `synthetic`. There is no in-process Orbbec option.
- `OrbbecSource` is not modified and not deleted. The child runs it as-is.
- Commit messages end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Pre-commit runs black/isort/autoflake and will reformat; re-`git add` and re-commit when it does.
- The Orbbec camera is currently connected. Tasks 1 and 8 require it; Tasks 2-7 do not.

---

### Task 1: Benchmark harness and baseline capture

Must be done **first**, against unmodified `HEAD`. The baseline is worthless if taken after any implementation work.

**Files:**
- Create: `tools/depth_bench.py`
- Create: `docs/superpowers/plans/depth-bench-baseline.json` (generated output, committed)

**Interfaces:**
- Consumes: nothing.
- Produces: `tools/depth_bench.py`, run as
  `PATASHADE_INPUT_DEVICE=9 .venv/bin/python tools/depth_bench.py --label <name> --seconds 60 --out <path.json>`.
  Writes a JSON object with keys `label`, `seconds`, `frames`, `fps`, `p50`, `p95`, `p99`, `max`, `over_30ms`, `over_50ms`, `over_100ms`.

- [ ] **Step 1: Write the benchmark harness**

Create `tools/depth_bench.py`:

```python
"""Measure the render loop's frame cadence with the depth camera running.

Committed rather than thrown away so the before and after arms run byte-identical
measurement code. The metric that matters is the tail, not the mean: GIL
contention from the depth thread leaves p50 untouched and wrecks p99.

    PATASHADE_INPUT_DEVICE=9 .venv/bin/python tools/depth_bench.py \
        --label before --seconds 60 --out baseline.json
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import program.program_conf  # noqa: F401,E402
from numeric_locale import restoreCNumericLocale  # noqa: E402
from PyQt5.QtCore import QTimer  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

SESSION = "saved/laignes.pnlive"


def build_scene(path):
    """Write the session's last state out as a plain scene file."""
    import json as _json

    with open(SESSION) as handle:
        live = _json.load(handle)

    with open(path, "w") as handle:
        _json.dump(live["states"][-1]["scene"], handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fps", type=float, default=72.0)
    parser.add_argument("--depth-source", default="orbbec")
    args = parser.parse_args()

    scene = "/tmp/depth_bench_scene.pn"
    build_scene(scene)

    the_app = QApplication(sys.argv[:1])
    restoreCNumericLocale()
    the_app.setStyle("Fusion")

    import app as app_module
    from gui.widgets.shader_widget import ShaderWidget

    stamps = []
    original = ShaderWidget.drawFrame

    def timed(self):
        try:
            return original(self)
        finally:
            stamps.append(time.perf_counter())

    ShaderWidget.drawFrame = timed

    app_args = argparse.Namespace(
        open=scene,
        debug=None,
        no_usb=None,
        use_shader_buffer=None,
        server=False,
        fps=args.fps,
        vsync="on",
        depth_source=args.depth_source,
    )

    patanode = app_module.PataShadeApp(app_args)
    patanode.show()
    patanode.openFile(scene)
    patanode.showShaderWindow()

    def report():
        # Drop the first 40 frames: startup, shader compilation and the
        # camera's first frames are not what this measures.
        warm = stamps[40:]
        intervals = sorted((b - a) * 1000 for a, b in zip(warm, warm[1:]))
        n = len(intervals)
        span = warm[-1] - warm[0]

        result = {
            "label": args.label,
            "seconds": args.seconds,
            "depth_source": args.depth_source,
            "frames": len(warm),
            "fps": (len(warm) - 1) / span,
            "p50": intervals[n // 2],
            "p95": intervals[int(n * 0.95)],
            "p99": intervals[int(n * 0.99)],
            "max": intervals[-1],
            "over_30ms": sum(1 for x in intervals if x > 30),
            "over_50ms": sum(1 for x in intervals if x > 50),
            "over_100ms": sum(1 for x in intervals if x > 100),
        }

        with open(args.out, "w") as handle:
            json.dump(result, handle, indent=2)

        print(json.dumps(result, indent=2))
        the_app.quit()

    QTimer.singleShot(int(args.seconds * 1000), report)
    the_app.exec_()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the baseline against today's code**

Confirm the tree is at `HEAD` with nothing uncommitted, the camera is connected, then:

```bash
git status --porcelain | grep -v '^??'   # must print nothing
lsusb | grep -i 2bc5                      # must show the Orbbec Gemini
PATASHADE_INPUT_DEVICE=9 .venv/bin/python tools/depth_bench.py \
    --label before --seconds 60 \
    --out docs/superpowers/plans/depth-bench-baseline.json
```

Expected, from the measurement that motivated this work: `fps` around 66-67, `p99` around 22 ms. If `fps` comes back at ~72 and `p99` at ~15 ms, **stop** — the camera is not actually streaming (check `--depth-source orbbec` took effect and `lsusb` shows the device), because that is the *target* number, not the baseline.

- [ ] **Step 3: Commit the harness and the baseline**

```bash
git add tools/depth_bench.py docs/superpowers/plans/depth-bench-baseline.json
git commit -m "test(depth): add the frame-cadence benchmark and record the baseline

Captured against HEAD with the camera streaming, before any process-split
work, so the after arm has something honest to beat. Committed rather than
run ad hoc so both arms execute byte-identical measurement code.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: The shared-memory frame ring

Pure data structure, no processes. Testable entirely in one process.

**Files:**
- Create: `depth/depth_process.py`
- Test: `tests/depth/test_depth_process.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `HEADER_SIZE = 4096`
  - `class FrameRing` with classmethods `create(width, height) -> FrameRing` and `attach(name) -> FrameRing`, instance attributes `name: str`, `width: int`, `height: int`, methods `write(frame: np.ndarray) -> None`, `read(last_seq: int) -> tuple[np.ndarray | None, int]`, `close() -> None`, `unlink() -> None`.
  - `read` returns `(None, last_seq)` when no new frame is available, else `(frame, new_seq)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/depth/test_depth_process.py`:

```python
"""The shared-memory transport between the depth child and the render process."""

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_process.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'depth.depth_process'`

- [ ] **Step 3: Implement the frame ring**

Create `depth/depth_process.py`:

```python
"""Depth capture in a child process, so its GIL cost cannot stall rendering.

The Orbbec filter chain holds the GIL for about 68% of the 14.5 ms it spends
on each frame. At 31 fps that is roughly 306 ms a second during which no other
Python in the process can run -- including the render loop. Measured against
the real camera, in-process capture costs 5 fps and pushes the p99 frame
interval from 15.6 ms to 22.7 ms.

A child process has its own GIL, so the filters stop competing with rendering
and all five can be kept rather than traded away for frame rate.
"""

from multiprocessing import shared_memory

import numpy as np

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

        # Deliberately no resource_tracker.unregister here. An earlier draft
        # called it to suppress the "leaked shared_memory objects" warning an
        # attaching process prints on exit -- but the tracker fd is inherited
        # by children under both spawn and fork, so all processes share one
        # table, and unregistering here only races the creator's unlink and
        # prints a KeyError traceback on every clean shutdown. Measured: it
        # buys no safety either, since a creator killed before it unlinks
        # leaks the segment whether or not anyone unregistered. On the normal
        # path the creator's unlink() clears the entry and nothing warns; on
        # the abnormal path the warning is the honest signal.
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_process.py -v`
Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
git add depth/depth_process.py tests/depth/test_depth_process.py
git commit -m "feat(depth): add the shared-memory frame ring

Double-buffered uint16 frames with a sequence counter instead of a lock: the
writer fills the slot the reader is not looking at, publishes it, then bumps
seq; the reader samples seq, copies, and re-samples, discarding the attempt if
the writer overtook it.

Newest-wins by construction, which is why this is shared memory and not a
Queue -- a queue would hand the render process a backlog of stale depth frames
whenever it fell behind, and for live visuals the newest frame is the only one
worth having.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: The child process entry point

**Files:**
- Modify: `depth/depth_process.py`
- Test: `tests/depth/test_depth_process.py`

**Interfaces:**
- Consumes: `FrameRing` from Task 2.
- Produces:
  - `def _child_main(conn, source_factory=None) -> None`
  - Protocol, parent → child: `("stream",)`, `("stop",)`, `("shutdown",)`
  - Protocol, child → parent: `("ready", shm_name, width, height, depth_scale)`, `("error", message)`, `("stopped",)`
  - `POLL_INTERVAL_S = 0.05`

- [ ] **Step 1: Write the failing tests**

Append to `tests/depth/test_depth_process.py`:

```python
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
```

Add `import time` to the module's imports if it is not already there.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_process.py -k child -v`
Expected: FAIL, `ImportError: cannot import name '_child_main'`

- [ ] **Step 3: Implement the child**

Append to `depth/depth_process.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_process.py -v`
Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
git add depth/depth_process.py tests/depth/test_depth_process.py
git commit -m "feat(depth): add the depth child process entry point

A loop around whatever source it is handed, which in production is
OrbbecSource -- the same class, with the same profile selection, the same
filter chain and the same error messages that ran in-process before. Capture
is relocated, not rewritten, so its existing tests keep covering it.

Control is a Pipe carrying only small messages: the child answers 'stream'
with the post-chain dimensions the parent cannot know in advance, and reports
any failure to open as an error the engine can surface verbatim.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: ProcessSource — open, read, close

**Files:**
- Modify: `depth/depth_process.py`
- Test: `tests/depth/test_depth_process.py`

**Interfaces:**
- Consumes: `FrameRing`, `_child_main` from Tasks 2-3.
- Produces:
  - `class ProcessSource(DepthSource)` with `__init__(self, child_target=None)`, `open() -> (width, height, depth_scale)`, `read() -> np.ndarray | None`, `close() -> None`
  - `OPEN_TIMEOUT_S = 15.0`
  - `def _reset_child_for_tests() -> None`

- [ ] **Step 1: Write the failing tests**

Append to `tests/depth/test_depth_process.py`:

```python
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


def test_read_returns_frames_then_none_until_the_next_one():
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
    finally:
        source.close()


def test_read_before_open_is_an_error():
    source = ProcessSource(child_target=child_with_fake_source)

    with pytest.raises(DepthSourceError):
        source.read()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_process.py -k "open_returns or read_returns or read_before" -v`
Expected: FAIL, `ImportError: cannot import name 'ProcessSource'`

- [ ] **Step 3: Implement ProcessSource and the child handle**

Append to `depth/depth_process.py`:

```python
import multiprocessing
import time

from depth.depth_source import DepthSource, DepthSourceError

# How long open() waits for the child to report. A cold child pays a fresh
# interpreter, the pyorbbecsdk import and the camera open; 15 s is generous
# for all three and still bounded. This wait happens on DepthEngine's capture
# thread, never on the GUI thread, so rendering is unaffected by it.
OPEN_TIMEOUT_S = 15.0

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
        # The parent's copy of the child end is dead weight, and leaving it
        # open means the child never sees EOF if the parent dies.
        child_conn.close()

    def start_stream(self):
        self.ensure_started()
        self.conn.send(("stream",))

        if not self.conn.poll(OPEN_TIMEOUT_S):
            raise DepthSourceError(
                "depth process did not report within %ss" % OPEN_TIMEOUT_S
            )

        message = self.conn.recv()

        if message[0] == "error":
            raise DepthSourceError(message[1])

        if message[0] != "ready":
            raise DepthSourceError("unexpected message from depth process: %r" % (message,))

        return message[1], message[2], message[3], message[4]

    def stop_stream(self):
        if not self.alive():
            return
        try:
            self.conn.send(("stop",))
        except (BrokenPipeError, OSError):
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

        if self.conn is not None:
            try:
                self.conn.close()
            except OSError:
                pass

        self.process = None
        self.conn = None


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


import atexit  # noqa: E402

atexit.register(_shutdown_at_exit)


class ProcessSource(DepthSource):
    """A DepthSource whose capture runs in another process.

    Implements the same three methods as OrbbecSource, so DepthEngine,
    DepthInput and DepthStatus need no knowledge that anything changed.
    """

    def __init__(self, child_target=None):
        self._target = child_target or _default_child_target
        self._ring = None
        self._last_seq = 0

    def open(self):
        child = _get_child(self._target)
        name, width, height, scale = child.start_stream()

        self._ring = FrameRing.attach(name)
        self._last_seq = 0

        return width, height, scale

    def read(self):
        if self._ring is None:
            raise DepthSourceError("read() on a ProcessSource that is not open")

        frame, seq = self._ring.read(self._last_seq)
        self._last_seq = seq

        return frame

    def close(self):
        if self._ring is not None:
            self._ring.close()
            self._ring = None

        child = _child
        if child is not None:
            child.stop_stream()


def _default_child_target(conn):
    """Module-level so spawn can pickle it by qualified name."""
    _child_main(conn)
```

Move the `import multiprocessing`, `import time` and `from depth.depth_source import ...` lines to the top of the file with the other imports; isort will enforce this.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_process.py -v`
Expected: PASS, 14 tests.

- [ ] **Step 5: Commit**

```bash
git add depth/depth_process.py tests/depth/test_depth_process.py
git commit -m "feat(depth): add ProcessSource, the parent side of depth capture

Implements the same three methods as OrbbecSource -- open, read, close -- so
DepthEngine, DepthInput and DepthStatus need no knowledge that capture moved.

The process lives in a module-level singleton rather than in the source,
because DepthEngine builds a fresh source from the factory on every retry: a
release and re-acquire would otherwise kill and respawn the child, and a live
session cycling states would pay seconds of black depth each time. Global
state is the ugly part of this; killing the child on every release would be
cleaner code and worse behaviour.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Failure handling — death, wedging, restart

**Files:**
- Modify: `depth/depth_process.py`
- Test: `tests/depth/test_depth_process.py`

**Interfaces:**
- Consumes: `ProcessSource` from Task 4.
- Produces: `WEDGE_TIMEOUT_S = 5.0`; `ProcessSource.read()` raises `DepthSourceError` when the child has exited or has published nothing for `WEDGE_TIMEOUT_S`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/depth/test_depth_process.py`:

```python
import depth.depth_process as depth_process


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


def test_a_frame_resets_the_wedge_timer(monkeypatch):
    monkeypatch.setattr(depth_process, "WEDGE_TIMEOUT_S", 1.0)
    source = ProcessSource(child_target=child_with_fake_source)
    try:
        source.open()

        # FakeSource produces continuously, so two seconds of reading must not
        # trip a one second timeout.
        deadline = time.time() + 2.0
        while time.time() < deadline:
            source.read()
            time.sleep(0.02)
    finally:
        source.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_process.py -k "dead_child or silent_child or wedge_timer" -v`
Expected: FAIL — `read()` returns `None` forever instead of raising.

- [ ] **Step 3: Implement failure detection**

In `depth/depth_process.py`, add the constant beside `OPEN_TIMEOUT_S`:

```python
# How long a live-but-silent child gets before it is treated as wedged. About
# 155 missed frames at 31 fps, so it cannot fire on a merely slow frame. The
# cost of it being wrong in the other direction is 5 s of frozen depth before
# recovery starts.
WEDGE_TIMEOUT_S = 5.0
```

Replace `ProcessSource.__init__`, `open` and `read`:

```python
    def __init__(self, child_target=None):
        self._target = child_target or _default_child_target
        self._ring = None
        self._last_seq = 0
        self._last_frame_at = None

    def open(self):
        child = _get_child(self._target)
        name, width, height, scale = child.start_stream()

        self._ring = FrameRing.attach(name)
        self._last_seq = 0
        self._last_frame_at = time.monotonic()

        return width, height, scale

    def read(self):
        if self._ring is None:
            raise DepthSourceError("read() on a ProcessSource that is not open")

        frame, seq = self._ring.read(self._last_seq)
        self._last_seq = seq

        if frame is not None:
            self._last_frame_at = time.monotonic()
            return frame

        # No frame this tick, which is normal -- the camera runs at 31 fps and
        # this is called far more often. It stops being normal if the child has
        # gone, or has stopped producing entirely: both are disconnects, and
        # DepthEngine already knows how to back off and rebuild a source.
        child = _child

        if child is None or not child.alive():
            code = None if child is None or child.process is None else child.process.exitcode
            raise DepthSourceError("depth process exited (code %s)" % code)

        silent_for = time.monotonic() - self._last_frame_at

        if silent_for > WEDGE_TIMEOUT_S:
            raise DepthSourceError(
                "no depth frame from the capture process in %.1fs" % silent_for
            )

        return None
```

Note the wedge check reads the module attribute through `depth_process.WEDGE_TIMEOUT_S` at call time only if written as a bare global reference; keep the bare name `WEDGE_TIMEOUT_S` so `monkeypatch.setattr` on the module takes effect.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_process.py -v`
Expected: PASS, 17 tests.

- [ ] **Step 5: Commit**

```bash
git add depth/depth_process.py tests/depth/test_depth_process.py
git commit -m "feat(depth): detect a dead or wedged capture process

read() returning None is normal -- the camera runs at 31 fps and the engine
polls far faster. It stops being normal when the child has exited, or has
published nothing for 5 s while still alive. Both are disconnects, and raising
DepthSourceError hands them to machinery that already exists: DepthEngine
closes the source, rebuilds one from the factory and retries with backoff from
1 s to 30 s, which is what respawns the child.

5 s is about 155 missed frames at 31 fps, so it cannot fire on a slow frame.

Visuals keep rendering on the last depth frame throughout, which is the point:
after this a dead or absent camera can no longer stall the render loop.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Keep the child alive across close and reopen

**Files:**
- Modify: `depth/depth_process.py` (only if the tests fail)
- Test: `tests/depth/test_depth_process.py`

**Interfaces:**
- Consumes: everything from Tasks 2-5. Adds no new names.

- [ ] **Step 1: Write the failing tests**

Append to `tests/depth/test_depth_process.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they pass or fail**

Run: `.venv/bin/python -m pytest tests/depth/test_depth_process.py -k "reopening or replaced or does_not_kill" -v`

These should already pass on Task 4's implementation — `close()` calls `stop_stream()`, not `shutdown()`, and `ensure_started()` respawns only when the process is dead. If any fails, fix `ProcessSource.close` and `_Child.ensure_started` until it passes; do not weaken the test.

- [ ] **Step 3: Commit**

```bash
git add tests/depth/test_depth_process.py
git commit -m "test(depth): pin the capture process's lifetime across reopen

close() must stop the stream without killing the process, and open() must
respawn only when it has actually died. A live session cycling through states
releases and re-acquires the engine, and respawning there would cost a fresh
interpreter, the SDK import and a camera open -- seconds of black depth,
mid-set.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Wire it into the factory

**Files:**
- Modify: `depth/depth_source.py` (`make_source_factory`, around line 379)
- Modify: `tests/depth/test_app_wiring.py:50`
- Modify: `tests/depth/test_depth_source.py:516-517`

**Interfaces:**
- Consumes: `ProcessSource` from Task 4.
- Produces: `make_source_factory("orbbec")` returns `ProcessSource`; `make_source_factory("synthetic")` returns `SyntheticSource`.

- [ ] **Step 1: Update the three existing assertions**

In `tests/depth/test_app_wiring.py`, replace the `OrbbecSource` import with `ProcessSource` from `depth.depth_process`, and line 50:

```python
    assert isinstance(make_source_factory("orbbec")(), ProcessSource)
```

In `tests/depth/test_depth_source.py`, import `ProcessSource` from `depth.depth_process` and replace lines 516-517:

```python
    assert isinstance(make_source_factory("orbbec")(), ProcessSource)
    assert isinstance(make_source_factory("anything-else")(), ProcessSource)
```

Leave every other use of `OrbbecSource` in that file alone: the child runs that class, and its coverage of the filter chain, profile selection and post-chain dimensions is exactly what keeps this safe.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/depth/ -k source_factory -v`
Expected: FAIL — the factory still returns `OrbbecSource`.

- [ ] **Step 3: Point the factory at the child process**

In `depth/depth_source.py`, replace `make_source_factory`:

```python
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
```

The import is function-local because `depth_process` imports from `depth_source`; at module scope it would be circular.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS. The count should be the previous total plus the new `test_depth_process.py` tests.

- [ ] **Step 5: Commit**

```bash
git add depth/depth_source.py tests/depth/test_app_wiring.py tests/depth/test_depth_source.py
git commit -m "feat(depth): run the camera in a child process by default

--depth-source orbbec now yields a ProcessSource. There is deliberately no
in-process option: two ways to run the camera would mean two behaviours to
reason about when something goes wrong, and the in-process one is what this
work exists to retire.

OrbbecSource is untouched and still directly tested -- it is what the child
runs, so its coverage of the filter chain, profile selection and post-chain
dimensions is exactly what makes this safe.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Prove the gain

Requires the camera connected.

**Files:**
- Create: `docs/superpowers/plans/depth-bench-after.json`
- Modify: `docs/superpowers/specs/2026-08-17-depth-capture-process-design.md` (results section)

**Interfaces:**
- Consumes: `tools/depth_bench.py` and `depth-bench-baseline.json` from Task 1.

- [ ] **Step 1: Run the after arm**

Identical command, identical duration, same machine, camera connected:

```bash
lsusb | grep -i 2bc5
PATASHADE_INPUT_DEVICE=9 .venv/bin/python tools/depth_bench.py \
    --label after --seconds 60 \
    --out docs/superpowers/plans/depth-bench-after.json
```

- [ ] **Step 2: Compare**

```bash
.venv/bin/python - <<'PY'
import json
before = json.load(open("docs/superpowers/plans/depth-bench-baseline.json"))
after = json.load(open("docs/superpowers/plans/depth-bench-after.json"))
print("%-12s %10s %10s" % ("metric", "before", "after"))
for key in ("fps", "p50", "p95", "p99", "max", "over_30ms", "over_50ms"):
    print("%-12s %10.2f %10.2f" % (key, before[key], after[key]))
PY
```

**Pass criteria**, from the in-process A/B that motivated this work (66.86 fps / p99 22.66 ms with the chain, 71.96 fps / p99 15.63 ms without it):

- `fps` ≥ 71.0
- `p99` ≤ 17.0 ms
- `p50` unchanged within 0.5 ms — it was never the problem, and a change there means something else moved

If `fps` lands between 68 and 71, the split worked but something still contends: re-run with `PATANODE_FREEZE_LOG=1` and read the stacks before declaring victory. Do not adjust the pass criteria to fit the result.

- [ ] **Step 3: Record the result in the spec**

Append a `## Result` section to `docs/superpowers/specs/2026-08-17-depth-capture-process-design.md` containing the comparison table from Step 2, stating the date, that the camera was connected, and whether the pass criteria were met. If they were not, say so plainly and describe what the freeze log showed.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/depth-bench-after.json docs/superpowers/specs/2026-08-17-depth-capture-process-design.md
git commit -m "test(depth): record the after measurement for the process split

Same harness, same duration, same machine, camera connected.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Manual check with the real session**

Not automatable, and the thing that actually matters:

1. `PATASHADE_INPUT_DEVICE=9 .venv/bin/python main.py --fps 72` — open `saved/laignes.pnlive`, play it, confirm depth still drives the visuals and the picture looks as it did.
2. Unplug the camera mid-run. Visuals must keep rendering on the last depth frame; the Depth Input node's tooltip must report unavailable; the render loop must not stall.
3. Plug it back in. Depth must recover within the backoff window without a restart.
4. Quit cleanly. No orphaned `depth-capture` process (`pgrep -f depth-capture` prints nothing) and no leftover block in `/dev/shm`.

---

## Notes for the implementer

**Out of scope**, both real and both measured, deliberately not bundled so they cannot muddy the Task 8 comparison:

- `create_bmp_in_memory` runs every frame for every graph and the result is usually discarded — 4,765 calls costing 2,113 ms over 70 s, about 30 ms/s.
- A gen-2 GC pause of ~71 ms fires roughly once a minute; `gc.freeze()` after startup takes it to 0.8 ms.

**If you get stuck on spawn pickling:** every child target must be a module-level function. A closure or a lambda will fail with `AttributeError: Can't pickle local object`. That is why `_default_child_target` and the test targets are module-level rather than defined inline.

**If `/dev/shm` accumulates files:** the child unlinks in its `finally`, but a `SIGKILL`ed child cannot. `ls /dev/shm` between runs while developing; stale blocks are harmless but confusing.

**On block naming:** the spec says the name should make a leaked block impossible to confuse with the next run's. `SharedMemory(create=True)` already assigns a random unique name, which satisfies that, so no explicit pid in the name is needed — this is a simplification of the spec, not an omission from it.
