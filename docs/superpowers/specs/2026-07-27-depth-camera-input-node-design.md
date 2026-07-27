# Depth Camera Input Node — Design

**Date:** 2026-07-27
**Branch:** `feat/gemini_depth_capture`
**Status:** Approved, ready for implementation planning

## Goal

Make the Orbbec Gemini 2 depth stream available inside the PataNode graph as a
texture, so shaders can sample distance the way they sample any other input.

Today the camera exists only as two standalone scripts in `TODO/`
(`gemini_sdk_test.py` reads depth via `pyorbbecsdk`, `gemini_test.py` probes the
colour stream over V4L2). Neither touches the node graph.

## Scope

**In scope:** depth stream only, as a single output texture on a single node
type, with the capture running off the render thread and degrading gracefully
when no camera is present.

**Out of scope:** the colour stream, the IR stream, depth-to-colour alignment,
point clouds, and any effect that consumes depth. Those are separate specs. A
later depth-driven effect needs no change to this node — it connects to the
output socket like any other texture producer.

## Decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Streams exposed | Depth only | Smallest useful thing; colour/IR/alignment each add SDK surface without serving the first effect. |
| Capture ownership | App-level `DepthEngine` | Matches `AudioEngine`/`LightEngine`. One camera shared by any number of nodes, surviving scene load and reload. Node-owned threads would fight over the USB device. |
| Depth → texture | Raw `uint16` upload, normalise in GLSL | Zero per-frame CPU work; `near`/`far` become live shader uniforms instead of forcing a re-upload on every tweak. |
| Unmeasured pixels | Depth in `.rgb`, validity in `.a` | One shader branch, no cost. Downstream effects mask on alpha or ignore it. |
| Missing camera | Degrade gracefully, auto-reconnect | Live-performance tool. Saved scenes containing a depth node must open on a machine with no camera. |
| Engine startup | Lazy, refcounted on live nodes | No USB traffic for users who never use depth; no CLI flag to forget. |
| SDK isolation | Pluggable `DepthSource` | Lets the whole pipeline be developed and verified with no hardware, and confines the SDK to one swappable file. |
| Threading primitive | `threading.Thread`, not `QThread` | House pattern (`artnet/controller.py:201`, `server/server.py:102`). `AudioEngine` already has this exact shape: non-Qt producer, `QTimer` pull. Signals would deliver every frame, defeating the latest-wins drop policy. |

## Architecture

The engine is a top-level package, matching `audio/` and `light/` — it is an
app-level service, not a program.

```
depth/
  __init__.py
  depth_source.py     DepthSource interface, OrbbecSource, SyntheticSource
  depth_engine.py     capture thread, reconnect, frame slot, refcount
program/input/depth_input/
  __init__.py
  depth_input.py      DepthInput(ProgramBase) + DepthInputNode(ShaderNode, Texture)
  depth_input.glsl
```

Three units, each understandable without reading the others:

- **`DepthSource`** knows the SDK. It knows nothing about threads or OpenGL.
- **`DepthEngine`** knows threads and lifetime. It knows nothing about the SDK
  or OpenGL.
- **`DepthInput` / `DepthInputNode`** know OpenGL. They know nothing about
  threads or the SDK.

### Data flow, one frame

1. The capture thread calls `source.read()`, receives an `(h, w)` `uint16`
   array, and swaps it into a single slot with `frame_id += 1`.
2. On the main thread, `render()` calls `engine.get_frame(since=self._last_frame_id)`,
   which returns `None` when nothing is new. The camera runs at 10 fps and the
   render loop far faster, so most renders re-blit the existing texture.
3. On a new frame: if no texture exists, or the dimensions changed (a reconnect
   can return a different profile), allocate
   `ctx.texture((w, h), components=1, dtype="u2")` with `NEAREST` filtering.
   Then `texture.write(array)`.
4. Bind, set uniforms, render the fullscreen quad into the standard
   `[win_size, 4, "f4"]` FBO. The blit rescales sensor resolution to the graph's
   working resolution.

Frames the renderer misses are dropped. The slot is latest-wins, never a queue,
so a stalled main thread cannot grow a backlog.

## `DepthSource`

```python
class DepthSource:
    def open(self) -> tuple[int, int, float]:   # (width, height, depth_scale)
    def read(self) -> np.ndarray | None:        # (h, w) uint16, or None on timeout
    def close(self) -> None:
```

`read()` returning `None` means "no frame within the timeout" and is normal.
Failure is signalled by raising; the engine treats any exception as a
disconnect.

### `OrbbecSource`

The only file that imports `pyorbbecsdk`, and it imports **inside `open()`** so
a missing SDK surfaces as an ordinary failed connection rather than an import
crash at startup.

Wraps `Pipeline` / `Config` / `OBSensorType.DEPTH_SENSOR` as in
`TODO/gemini_sdk_test.py`. Uses the default depth stream profile. Known working
profile on this hardware: **1280×800 @ 10 fps**. `wait_for_frames` gets a
**200 ms** timeout — at 10 fps a frame arrives every 100 ms, and the 100 ms used
in the test script sits close enough to the frame period to time out constantly.

`read()` returns `np.frombuffer(frame.get_data(), dtype=np.uint16).reshape((h, w))`,
copied so the SDK is free to reuse its buffer.

### `SyntheticSource`

Generates a 1280×800 `uint16` depth ramp at 10 fps — deliberately matching the
real profile so timing behaviour during development matches the camera. Contains
a moving blob at a plausible distance and a punched region of zeros, so the hole
path and the alpha channel are exercised without hardware. Selected by
`--depth-source synthetic`.

## `DepthEngine`

**Construction.** `app.py` always builds the object, alongside the existing
engines: `self.depth_engine = DepthEngine(source_factory)`. It starts idle — no
thread, no USB traffic. The factory comes from a new
`--depth-source {orbbec,synthetic}` argument on `main.py`, defaulting to
`orbbec`.

**Refcount.** `DepthInputNode.__init__` calls `acquire()`; the node overrides
nodeeditor's `remove()` to call `release()`. The first acquire starts the
thread; the last release stops it and closes the device. Two depth nodes share
one camera and one upload. Scene load creates nodes through the normal path, so
reopening a saved graph is covered.

**Capture loop.**

```
while running:
    if source not open:
        try open  -> STREAMING, reset backoff
        on failure -> UNAVAILABLE(reason), sleep(backoff),
                      backoff = min(backoff * 2, 5s), continue
    frame = source.read()          # blocks up to 200ms
    if frame is None: continue     # timeout, not an error
    on exception -> close source, UNAVAILABLE, back to reconnect
    with lock: slot = (frame_id + 1, array, w, h, depth_scale)
```

Backoff starts at 1 s and caps at 5 s, so an absent camera costs one probe every
five seconds rather than a spin. A mid-set unplug raises from `read()`, enters
the same reconnect path, and recovers on its own when the cable returns.

**The slot.** One tuple behind a `threading.Lock`. `get_frame(since)` returns
`None` if `frame_id == since`, otherwise the tuple. The capture thread allocates
a fresh array per frame and never mutates a published one, so the main thread
may read it outside the lock without tearing.

**Status.** A `status` property (`IDLE`, `CONNECTING`, `STREAMING`,
`UNAVAILABLE`) plus a human-readable reason. The node writes it into
`grNode.setToolTip()`, so "no camera" is visible in the UI rather than silently
black. Status is polled, not pushed — the node reads it during `render()`.

**Shutdown.** `close()` clears `running` and joins with a timeout, wired into
the app exit path. The thread is a daemon, so a missed join cannot hang the
process.

## `DepthInput` program and node

**Registration.** `OP_CODE_DEPTH_INPUT = name_to_opcode("DepthInput")`, with
`@register_program` on the program and `@register_node` on the node, following
`program/scene/texture/texture.py`.

**Node.** `DepthInputNode(ShaderNode, Texture)` — `inputs=[]`, `outputs=[3]`,
appearing under the "Textures" palette category. `Texture` rather than `Input`:
`Input` is where `StdInput` lives and carries graph-container proxy semantics
this node has nothing to do with. `render()` mirrors `TextureNode.render()` —
`norender()` when `already_called`, otherwise `render()`.

**Program.** `DepthInput(ProgramBase)` — one FBO at `[win_size, 4, "f4"]`, the
standard `SQUARE_VERT_PATH` vertex shader, `depth_input.glsl` fragment.

**Parameters**, all via `add_float_cpu_adaptable_parameter` (`ProgramBase`
offers only float and text widgets, so the flips are floats):

| Name | Default | Meaning |
| --- | --- | --- |
| `near_mm` | 500 | Distance mapping to 0.0 |
| `far_mm` | 4000 | Distance mapping to 1.0 |
| `flip_x` | 0 | Mirror horizontally (0 or 1) |
| `flip_y` | 0 | Mirror vertically (0 or 1) |

Because normalisation is `(mm - near) / (far - near)`, setting `far_mm < near_mm`
inverts the ramp so near objects read bright. No extra uniform — worth
documenting on the node.

`bindUniform` reads these four parameters from `getCpuAdaptableParameters()`,
passes `near_mm` and `far_mm` through unchanged, and combines the two flip
floats into the single `vec2 flip` uniform the shader expects. `depth_scale`
comes from the frame tuple published by the engine, not from a parameter — it is
a property of the sensor, not a user control.

**The always-valid texture.** `initParams` allocates a 1×1 `u2` texture holding
zero, so the shader has something bindable before the first frame arrives. Raw
`0` already means "no measurement", so a camera that never connects produces
exactly the same output as a hole: `vec4(0)`, alpha 0. "No data" and "no camera"
collapse into one downstream case instead of two.

## Shader

```glsl
#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
// R16UI: integer sampler, NEAREST only. Linear filtering across a depth
// discontinuity interpolates foreground into background and invents surfaces.
uniform usampler2D depth_map;
uniform float near_mm;
uniform float far_mm;
uniform float depth_scale;   // raw units -> mm, reported by the sensor
uniform vec2 flip;

void main() {
    vec2 uv = gl_FragCoord.xy / iResolution.xy;
    uv = mix(uv, 1.0 - uv, flip);

    uint raw = texture(depth_map, uv).r;
    if (raw == 0u) {           // unmeasured pixel, or no camera yet
        fragColor = vec4(0.0);
        return;
    }

    float mm = float(raw) * depth_scale;
    float d = clamp((mm - near_mm) / (far_mm - near_mm), 0.0, 1.0);
    fragColor = vec4(vec3(d), 1.0);
}
```

`bindUniform` calls `super().bindUniform(af)` first, which supplies
`iResolution`.

**`usampler2D` is unlike every other shader in this repo.** `dtype="u2"` yields
a `GL_R16UI` texture, sampled as an integer sampler returning raw integers, not
a float `sampler2D`. This is the correct choice: integer textures cannot be
linearly filtered, and linear filtering across a depth edge fabricates surfaces
between foreground and background. The comment in the shader exists so nobody
"fixes" it to `sampler2D` later.

**Aspect ratio.** `uv = gl_FragCoord.xy / iResolution.xy` stretches the sensor
image to fill the FBO. The depth stream is 1.6:1 against a 16:9 target, so a
person renders slightly wide. Filling the frame is almost always what a VJ tool
wants, and a `fit` parameter is a two-line addition later if the distortion
proves annoying in practice.

## Dependency and packaging

`pyorbbecsdk` is **not currently importable in `.venv`**, and it is not in
`pyproject.toml`.

The package is published as `pyorbbecsdk2` on GitHub releases, not on PyPI, and
building from source is broken (the repo's git-LFS remote is missing objects).
It is installed from the prebuilt wheel — for Python 3.11 / linux x86_64,
`pyorbbecsdk2-2.1.1-cp311-cp311-linux_x86_64.whl`. The import name is
`pyorbbecsdk`. Non-root USB access needs the bundled udev rules installed and
the camera replugged. The Gemini 2 must be on a USB 3.0 port; on a 480M link it
drops off the bus mid-enumeration.

Given the non-PyPI source and the graceful-degradation decision, the SDK stays
an **optional, manually installed dependency**, documented in the README rather
than listed in `pyproject.toml`. Nothing in the app imports it at startup.

## Verification

The repository has no test suite, so verification is by running the app. The
synthetic source is what makes that possible without hardware.

1. **No camera, no SDK** — launch, drop a Depth Input node. App does not crash,
   node renders black with alpha 0, tooltip reports the camera as unavailable.
   Save and reopen the scene; it loads cleanly.
2. **Synthetic source** — `--depth-source synthetic`. The moving blob is
   visible, the punched hole reads as alpha 0, and `near_mm`/`far_mm` visibly
   change the mapping. `far_mm < near_mm` inverts it. Both flips work.
3. **Real camera** — with hardware attached, confirm the profile reported is
   1280×800 @ 10 fps and that a hand at a known distance lands where `near_mm`
   and `far_mm` predict.
4. **Reconnect** — unplug mid-render. The node keeps rendering, the tooltip
   changes, the app stays responsive. Replug; streaming resumes without a
   restart.
5. **Refcount** — two depth nodes in one graph both render. Delete one; the
   other keeps streaming. Delete both; the capture thread stops.

## Implementation checks

Verify during implementation, not settled here:

- `name_to_opcode("DepthInput")` does not collide with a registered opcode. The
  function is a character sum, so collisions are possible.
- `node_conf.py` reaches `program.input`. It currently imports `program.scene`,
  `program.output`, `program.utils`, and `audio.transforms`; the depth node will
  not register without an import path to it.
- moderngl's `dtype="u2"` maps to `GL_R16UI` as expected on this driver, and
  `texture.write()` accepts the numpy array directly.
