# Motion Flow node — design

## Context

PataNode has plenty of nodes that consume a vector field — `fluid` takes a velocity texture as its
second input, `offset` warps by an offset, `sst` and `sobel` derive orientation from a still frame —
but nothing that produces one from actual movement. Every field in the graph was either
hand-parameterised or audio-driven.

Motion Flow watches whatever texture is plugged into it, measures how things moved since the last
frame, and emits that motion as a field other nodes can consume. The source can be a camera, the
Orbbec depth feed, or purely rendered content; the node does not care. Motion becomes a modulation
source alongside audio.

## Decisions

- **Source**: any texture input, not a camera-specific node.
- **Output**: one packed RGBA texture — `RG` = flow vector, `B` = motion magnitude, `A` = confidence.
- **Temporal**: decaying accumulation, so motion leaves a fading field rather than dying instantly.
- **Algorithm**: single-scale Lucas–Kanade at reduced resolution, plus Jacobi smoothing.
- **Audio**: no hardcoded coupling. Motion is itself the modulation source here; the params are
  ordinary exposed uniforms, mappable to audio through the existing system if wanted.

## Architecture

`program/utils/motion_flow/`, following `program/utils/fluid/fluid.py` (multi-pass program with
named sub-programs and Python-side ping-pong swaps) and `program/effects/orientationaa` (the
previous-frame memory pattern).

```
motion_flow.py      MotionFlow(ProgramBase) + MotionFlowNode(ShaderNode, Utils)
prefilter.glsl      RGB → luminance, downscaled, tent-blurred
flow.glsl           Lucas–Kanade 5×5 solve
smooth.glsl         one confidence-weighted Jacobi iteration
accum.glsl          temporal decay accumulation + gain + deadband
motion_flow.glsl    upscale to output res, pack RGBA
```

Registered in `program/utils/__init__.py`. Opcode is `name_to_opcode("motionflow")` = 1102, verified
free — that function sums character codes, so collisions are real (`opticalflow` would have collided
with `lumtriangle`).

### Resolution split

Flow is estimated at `compute_size = win_size // downscale`, default 4. `FBOManager.getFBO` hashes
each FBO's size independently, so mixed-resolution FBOs within one program work with no framework
change. Low-res passes bind `"iResolution": "compute_size"`; the output pass binds `win_size`.

`downscale` sizes the FBOs, which are allocated once at construction, so it is a constructor
argument rather than a live uniform.

**It also sets the maximum trackable speed**, which is the main tuning lever. Measured against
synthetic translation, accuracy versus displacement at `downscale=4`:

| displacement | 1 px/frame | 2 px | 4 px | 8 px |
|---|---|---|---|---|
| reported / true | 1.00 | 0.97 | 0.88 | 0.57 |

Each doubling of `downscale` doubles the trackable displacement: 8 px/frame reads 0.88 at
`downscale=8`, 16 px/frame reads 0.89 at `downscale=16`. Overshooting costs accuracy — 8 px/frame at
`downscale=16` collapses to 0.02, the detail having been blurred away. Rule of thumb: set
`downscale` to roughly the fastest motion expected, in pixels per frame.

This roll-off is inherent to single-scale Lucas–Kanade. A pyramidal version would handle large
displacements without the resolution trade, at roughly 3× the cost and considerably more code; it
was considered and rejected as premature.

### FBO layout — 7, all `4, "f4"`

| idx | size | role |
|-----|------|------|
| 0,1 | compute | luminance ping-pong — this frame / last frame |
| 2,3 | compute | flow ping-pong — LK output, then smoothing iterations |
| 4,5 | compute | accumulation ping-pong — temporal persistence |
| 6 | win_size | packed RGBA output |

Signed values need no encoding: `f4` attachments hold negatives directly.

### Per-frame passes

1. **prefilter** — luma + 3×3 tent into `fbo[0]`. The blur is load-bearing: LK on raw camera luma
   measures sensor noise rather than movement.
2. **flow** — 5×5 gaussian-weighted Lucas–Kanade against `fbo[1]`, the previous frame's luma.
   Diagonal damping is **proportional to gradient energy** (`lambda_reg * trace`), not absolute. A
   fixed lambda makes the damping depend on input contrast — at the original absolute default it was
   42% of the signal on a mid-contrast input, so a dim feed would have been crushed to zero while a
   bright one passed through. Confidence is Harris cornerness normalised by `trace²`, keeping it a
   contrast-independent 0..1 reading.
3. **smooth** — `smooth_iterations` (4) confidence-weighted Jacobi passes. Reliable vectors bleed
   into flat neighbourhoods, not the reverse; confidence diffuses alongside, so each iteration
   widens the region carrying a usable estimate. Measured to leave magnitude intact.
4. **accumulate** — whichever of the new flow or the decayed previous field is stronger wins, so
   fresh motion writes in at full amplitude while what is left behind fades geometrically. Blending
   instead would smear new movement against the trail it is replacing.

   The previous field is read through a semi-Lagrangian backtrace — sampled at `uv - v*drift`
   rather than at `uv` — so the field is carried along by its own velocity and a trail keeps
   travelling after the movement that made it has stopped. Unconditionally stable at any drift,
   needs no extra buffer since this pass already ping-pongs, and the source is clamped rather than
   wrapped so trails do not reappear on the opposite edge.
5. **output** — bilinear upscale, pack `RG`/`B`/`A`.

Then `fbo[0]/fbo[1]` swap, making this frame's luma next frame's reference.

**First-frame gate.** On frame 0 there is no previous luminance, and both buffers hold whatever the
FBO pool handed over, so the estimate is garbage. Because accumulation takes a max, that garbage
would latch and decay only slowly — at `persistence` 0.97, roughly a hundred frames of visible junk
on every scene load. `flow_valid` (internal, protected) forces a clean zero until a real previous
frame exists.

### Uniforms

Protected: `iChannel0`, `CurrLuma`, `PrevLuma`, `FlowTex`, `AccumTex`, `flow_valid`.

Exposed to the GUI and the mapping system — verified to be exactly these five, with no samplers:

| uniform | default | effect |
|---------|---------|--------|
| `flow_gain` | 1.0 | scales vector magnitude |
| `persistence` | 0.85 | 0 = instantaneous, →1 = long fading trails |
| `drift` | 1.0 | 0 = trails fade in place, 1 = travel at the speed that made them, >1 faster |
| `noise_threshold` | 0.002 | soft deadband below which motion is discarded |
| `lambda_reg` | 0.05 | damping as a fraction of gradient energy; higher = calmer |
| `magnitude_scale` | 8.0 | maps flow length into 0..1 for the `B` channel |

`smooth_iterations` is a Python attribute, not a uniform — the exposition system carries uniform
values, not loop counts.

Each of the five carries a plain-language description, its default, a lowest useful setting and an
exaggerated one, declared via `ProgramBase.initParameterDoc` in `initParams` and shown as a tooltip
in the Gpu parameters panel.

## Downstream wiring

`fluid`'s advect pass reads `texture(VelocityState, uv).xy` as a raw signed velocity, matching the
`RG` layout here in sign and channel order. **The units differ, though:** fluid divides its velocity
by resolution (`dt*vel/R*advect_amount` in `Ink/ink.glsl`), so it expects pixels per frame, while
this node emits uv per frame — a factor of ~1920 apart. The wiring works, but fluid's
`input_vel_intensity` has to go to roughly 1000 rather than its default of 10. An earlier draft of
this document claimed the two connected with no re-encoding; that was wrong about scale.

`offset` and mask-style nodes consume `B` as a motion mask. The `advect` node takes this field
directly and needs no rescaling, since it reads uv per frame.

Note that `A` (confidence) describes whether the *image structure* constrains the estimate — it is
high on a textured but motionless scene. `B` is the channel that reads motion presence.

## Verification

Verified headless against synthetic frames translated by known amounts
(harness: `test_motion_flow.py`, not currently in the repo):

- 1 px/frame in +x → reported +0.00103 uv/frame against 0.00104 expected, no spurious y.
- 2 px/frame in −y → −0.00357 against −0.00370, no spurious x.
- Still scene → exactly zero flow and magnitude, including on the first frames.
- `persistence=0` → field dies the instant motion stops. `persistence=0.97` → trail survives 5
  frames past the motion at 87% amplitude.
- `noise_threshold` above the signal → field fully suppressed.
- Allocation through the real `FBOManager`: 7 buffers at the two requested sizes, all distinct, and
  a second node shares none of them.
- Exposed uniform surface matches the five above exactly.

Remaining manual checks in the running app (`.venv/bin/python main.py`; keep numpy < 2.3):

1. Feed a camera into Motion Flow → Screen, wave a hand, confirm the field tracks and fades.
2. Wire it into Fluid's velocity input with an ink source on the first — fluid should be pushed
   around by real movement.
3. Save and reload a scene containing the node to confirm uniform serialisation round-trips.
