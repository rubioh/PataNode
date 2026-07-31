# Depth profile selection — design

Date: 2026-07-31
Status: approved
Supersedes nothing. Amends `2026-07-27-depth-camera-input-node-design.md`.

## Problem

`OrbbecSource.open()` selects its depth stream with
`profiles.get_default_video_stream_profile()` and trusts the result. The
returned profile's *pixel format* is whatever the device happens to advertise
first, and that varies with link speed and firmware.

On a USB 3.0 link (5000 Mbps) the Gemini 2 advertises 36 depth profiles and the
default is `1280x800 @30 OBFormat.RLE` — run-length compressed, so each frame is
a variable number of bytes. `read()` reshapes unconditionally:

```python
data = np.frombuffer(depth_frame.get_data(), dtype=np.uint16)
return data.reshape((self._height, self._width)).copy()
```

which fails on every frame:

    ValueError: cannot reshape array of size 8143 into shape (800,1280)

`DepthEngine._run` catches broad `Exception` on its read path, so this does not
crash. It does something worse: `open()` succeeds, the first `read()` raises,
the engine closes the device and reconnects with backoff, forever. The node
reports `unavailable`, renders transparent black, and the repeated failing
`open()` calls hold the GIL long enough to stall the render loop periodically.

Selecting `OBFormat.Y16` explicitly resolves it. Verified against the device:

```
selected 1280x800 @30 OBFormat.Y16
  frame 0:  78.2% valid, 198..2908mm, centre=2159mm, scale=1.0
60 good / 0 wrong-size in 2.1s (28.8 fps)
```

### Why this was not caught earlier

The camera previously enumerated at 480 Mbps on a USB 2 companion bus, where the
advertised profile list was narrower and its default happened to be an
uncompressed format. Every test uses a fake SDK module whose default profile is
uncompressed by construction, so the suite could not see it. The defect is in
*trusting the default*, and it was always there — the better cable only revealed
it.

The recorded "working profile is 1280x800 @10fps" was likewise an artefact of the
throttled link. At full link speed 30fps is available and works.

## Design

### 1. Demand Y16, prefer the best profile

`OrbbecSource.open()` replaces `get_default_video_stream_profile()` with a
selection pass over the advertised list:

- **Filter to `OBFormat.Y16`.** Y14 is bit-packed and RLE is compressed; neither
  survives `frombuffer(..., uint16).reshape()`. Excluding them by construction
  is what makes the choice safe, rather than hoping a default is sane.
- **Rank survivors against a preference list**, first match wins:

      (1280, 800, 30) → (1280, 800, 15) → (1280, 800, 10)
                      → (640, 400, 30)  → (640, 400, 15)

  A preference entry that is not advertised falls through to the next.
- **If no preference entry matches**, take the highest-resolution Y16 profile on
  offer (ties broken by highest fps). The preference list is an optimisation,
  not a requirement; an unusual device should still stream.
- **If no Y16 profile exists at all**, raise `DepthSourceError` naming the
  formats that *were* advertised. This is a real incompatibility, and the
  engine's existing status machinery already surfaces it as `unavailable (...)`.

The format constant and preference list live as module-level constants beside
`READ_TIMEOUT_MS`, so the policy is readable without tracing logic.

### 2. Guard the reshape

`read()` compares `data.size` against `self._width * self._height` before
reshaping. On mismatch it raises `DepthSourceError` carrying both numbers.

The engine already treats that as a read failure and reconnects, so behaviour is
unchanged — but the status reason becomes intelligible instead of a bare
`ValueError` about array shapes. This guard is what would have identified the
wrong format immediately, and it stays as the defence against any future format
surprise.

### 3. No change above the source boundary

`open()` still returns `(width, height, depth_scale)`; `read()` still returns an
`(h, w)` uint16 array. `DepthEngine`, `DepthInput` and the shader are untouched.
The node already reallocates its texture when a reconnect returns a different
size, so a fallback to 640x400 needs no further work.

This is the payoff of the original `DepthSource` boundary: a device-format bug
is fixed in one file, with no reasoning about threads or OpenGL.

## Testing

All tests use a fake SDK module and run with no camera attached, matching the
existing `tests/depth/test_depth_source.py` approach.

| Case | Assertion |
|---|---|
| Default profile is RLE, Y16 exists | Y16 profile selected — the exact regression |
| 1280x800@30 not advertised | Falls through to the next preference entry |
| No preference entry matches | Highest-resolution Y16 selected |
| Only RLE and Y14 advertised | `DepthSourceError`, message names the available formats |
| `read()` gets a short buffer | `DepthSourceError`, not `ValueError` |

The first case is the regression test: a fake whose default profile is RLE while
Y16 sits elsewhere in the list reproduces the failure exactly, and fails against
the current implementation.

## Out of scope

- **RLE decoding.** Y16 is advertised at every resolution and frame rate, so
  compression buys nothing for a local USB 3 link.
- **A `--depth-profile` flag.** The fallback policy removes the need to choose
  at launch, and adds no user-facing surface or argument validation.
- **Frame-rate throttling.** 30fps means roughly 61 MB/s of texture upload on
  the render thread. This cost has *not* been measured with the real camera —
  the orbbec path never completed a single upload, so the in-app diagnostic only
  ever timed the synthetic source. Manual verification is the first opportunity
  to observe it. If it does bite, lowering the first preference entry to
  `(1280, 800, 15)` is a one-line change.

## Documentation

The "working depth profile: 1280x800 @10fps" note is wrong at full link speed.
Correct it in the README and in project memory (`orbbec-gemini2-setup.md`),
recording that the *format* must be requested explicitly and that the default is
RLE on a USB 3 link. Left uncorrected it would send the next reader chasing a
bandwidth limit that no longer exists.
