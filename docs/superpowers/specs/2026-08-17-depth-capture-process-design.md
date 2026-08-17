# Depth capture in a separate process

## Why

The Orbbec filter chain added in `f10c434` runs five SDK filters on every depth
frame. Measured against the real camera on the target machine:

| Filter | p50 | p95 | max |
|---|---|---|---|
| DecimationFilter | 4.34 ms | 4.78 | 10.57 |
| ThresholdFilter | 0.11 ms | 0.13 | 0.16 |
| NoiseRemovalFilter | 5.94 ms | 6.06 | 6.23 |
| SpatialAdvancedFilter | 3.07 ms | 7.94 | 7.97 |
| TemporalFilter | 1.05 ms | 1.15 | 6.14 |
| **Whole chain** | **14.52 ms** | **15.21** | **20.80** |

The chain runs on the `depth-capture` thread, but **the SDK calls hold the
GIL for 68% of that time**. At the camera's 31 fps that is roughly 306 ms of
every second during which no other Python in the process can run — including
the render loop.

A/B against the real camera, same scene, 50 s per arm:

| | Full chain | Chain disabled |
|---|---|---|
| fps | 66.86 | **71.96** |
| frame interval p50 | 13.93 ms | 13.89 ms |
| frame interval p95 | 20.46 ms | **14.90 ms** |
| frame interval p99 | 22.66 ms | **15.63 ms** |

p50 is untouched and the tail is wrecked, which is the signature of
intermittent blocking rather than steady load. This also explains the freezes
reported during live sessions: stalls of 104-126 ms were captured with all
three threads competing (depth filtering, audio FFT, and the per-frame BMP
preview encode), two of them 85 ms apart — around 310 ms of near-continuous
freeze, which reads as roughly half a second.

Trimming the chain would fix the symptom by giving up the denoising it was
added for. A separate process fixes the cause: a child has its own GIL, so
the filter cost stops competing with rendering at all, and all five filters
can stay.

## Non-goals

- Changing what the filters do, or making the chain configurable.
- Moving anything else (audio, lights) out of process.
- Multiple simultaneous cameras.
- Fixing the per-frame BMP preview encode (measured 30 ms/s) or the gen-2 GC
  pause (63 ms, roughly once a minute). Both are real and both are separate.

## Architecture

One new file, `depth/depth_process.py`, containing the parent-side
`ProcessSource` and the child entry point. `make_source_factory` gains a
branch:

| `--depth-source` | Source | Notes |
|---|---|---|
| `orbbec` | `ProcessSource` | new default |
| `orbbec-inproc` | `OrbbecSource` | today's behaviour, kept for diagnosis |
| `synthetic` | `SyntheticSource` | unchanged |

**Nothing else changes.** `DepthEngine`, `DepthInput`, `DepthStatus`, the
retry/backoff logic and every existing depth test stay as they are. The seam
already exists: `DepthSource` is three methods.

```python
open()  -> (width, height, depth_scale)
read()  -> np.ndarray | None      # None means "nothing this tick"
close()
```

`DepthInput` only ever calls `get_frame`/`acquire`/`release`/`status_reason`
on the engine, so it is untouched by construction.

**The child reuses `OrbbecSource` unchanged.** Profile selection, the filter
chain, the "this SDK build has no X" errors and the post-chain dimension
measurement are all already written and tested. The child is a loop around
the class that exists today; capture is relocated, not reimplemented.

**Auto-restart comes for free.** `DepthEngine._run` already responds to any
`DepthSourceError` by calling `_safe_close(source)`, then rebuilding from the
factory and calling `open()` again, with backoff from 1 s doubling to 30 s.
So `ProcessSource.read()` raising when the child dies *is* the restart
mechanism. No new lifecycle code in the engine.

## Transport

Two channels, because control and bulk have different needs.

**Control — a `multiprocessing.Pipe`.** Small messages only:

- child → parent: `("ready", shm_name, width, height, depth_scale)`
- child → parent: `("error", message)`
- parent → child: `("stream",)`, `("stop",)`, `("shutdown",)`

The pipe is how the child reports post-chain dimensions, which the parent
cannot know in advance because decimation changes them.

**Frames — `multiprocessing.shared_memory`.** The child allocates the block
*after* opening the camera, once dimensions are known, and names it over the
pipe. Layout:

```
offset    0  seq          uint64   bumped before and after each write
offset    8  slot         uint32   which slot holds the latest complete frame
offset   12  width        uint32
offset   16  height       uint32
offset   20  depth_scale  float32
offset   24  (reserved)
offset 4096  slot 0       width * height * uint16
offset 4096 + frame_bytes  slot 1
```

Double-buffered with a sequence counter. The writer bumps `seq`, writes the
inactive slot, flips `slot`, bumps `seq` again. `read()` samples `seq`, copies
out, re-samples; if `seq` moved it retries. Single writer, single reader, no
locks.

This gives **latest-frame-wins**: if the parent falls behind it receives the
newest frame, never a backlog of stale ones. A `Queue` would buffer stale
depth frames, which is the wrong semantics for live visuals — that is the
reason for shared memory, not the bandwidth, which is trivial (320x200 uint16
is 128 KB, 4 MB/s at 31 fps).

`read()` returns `None` when `seq` has not moved. `DepthEngine` already treats
that as "timeout, not an error".

The parent must copy out of the slot rather than returning a view: the child
will overwrite it. One 128 KB copy per frame is negligible and matches what
`OrbbecSource.read` already does with `np.frombuffer`.

## Lifecycle

The child must outlive any single `ProcessSource`, because `DepthEngine`
builds a fresh source from the factory on every retry. A module-level `_Child`
singleton owns the `Process` and its pipe.

- `ProcessSource.open()` → `_Child.ensure_started()`, then `start_stream()`
- `ProcessSource.close()` → `stop_stream()`; the camera closes, the process
  stays alive
- Re-acquiring pays only the camera open (~2 s) instead of a fresh
  interpreter plus SDK import plus open (~5 s)
- App exit → an `atexit` hook requests clean shutdown; the process is also
  `daemon=True` so it can never outlive the parent

Lazy start is preserved: no `Depth Input` node means no `acquire()`, which
means no child process and no USB traffic. That is what the current design
intends and it should not regress.

The singleton is the weakest part of this design — global mutable state that
tests must reset between cases. The alternative, killing the child on every
release, is cleaner code and worse behaviour: state churn during a live
session would mean repeated multi-second gaps before depth returns. The trade
is deliberate.

`spawn`, not `fork`. Forking a process holding a GL context, Qt state and an
open camera is a source of exactly the intermittent failures this work exists
to remove.

## Failure handling

| Case | Detection | Response |
|---|---|---|
| Child exits | `read()` sees `not process.is_alive()` | `DepthSourceError` → engine backoff → respawn |
| Child wedges (alive, no frames) | `seq` unchanged for `WEDGE_TIMEOUT_S` | `DepthSourceError` → same path |
| Camera will not open | child sends `("error", msg)` | `open()` raises carrying that message → `UNAVAILABLE` and the SDK's real text in the node tooltip, as today |
| Spawn fails | exception in `ensure_started` | `DepthSourceError` |
| Parent dies | child is `daemon`, and sees pipe EOF | child exits |

`WEDGE_TIMEOUT_S = 5.0` — about 155 missed frames at 31 fps, so it cannot fire
on a merely slow frame.

Visuals keep rendering on the last depth frame throughout any of these. A dead
or absent camera can no longer stall the render loop, which is a second bug
fixed in passing: today a missing camera makes `Pipeline()` block the GIL on
every reconnect attempt.

**Shared memory cleanup.** The child unlinks its block in a `finally`. If the
child is `SIGKILL`ed the block leaks a file in `/dev/shm`; the name embeds the
child pid so a leak cannot collide with the next run. Python's
`resource_tracker` also warns when an attaching process exits, so the parent
unregisters the block after attaching to keep logs clean.

## Testing

The child target is injectable (`ProcessSource(child_target=...)`, defaulting
to the real one), so the parent side is testable without a camera:

- fake child emitting known frames → `open()` returns the right dimensions,
  `read()` returns those arrays
- latest-frame-wins: writer advances several frames while the reader is
  stalled; the reader gets the newest, not the oldest
- fake child that exits → `read()` raises `DepthSourceError`
- fake child that goes silent → wedge timeout fires
- fake child reporting `("error", …)` → `open()` raises carrying that message
- re-acquire after `close()` reuses the same process (assert pid is unchanged)
- the seqlock reader with no subprocess at all: write header and slots from
  the test process, read through the same code path, including a torn-read
  retry driven by mutating `seq` mid-copy

Existing `tests/depth/` is untouched. New tests land in
`tests/depth/test_depth_process.py`.

**Acceptance, measured against the real camera** with the same A/B harness
used to diagnose this: `--depth-source orbbec` should reach ~72 fps with p99
frame interval ~15 ms **while running all five filters** — matching the
chain-disabled arm above rather than the 66.86 fps / 22.66 ms p99 of the
in-process chain.

Secondary check: the freeze log (`PATANODE_FREEZE_LOG=1`) over a real session
should show the 104-126 ms stalls either gone or substantially rarer. They are
pile-ups involving audio and the preview encode as well, so this work removes
the dominant term but is not expected to eliminate them entirely.
