# Value Gradient — Design

**Date:** 2026-08-08
**Status:** Approved, ready for implementation planning

## Problem

`HSV Offset` shifts hue by a constant: `hsv.x += hue_offset` (`program/colors/hsv_offset/hsv_offset.glsl:40`). Every pixel moves by the same amount, so a monotone input — a grayscale mask, a single-hue render, a depth map — stays monotone. There is no way to get colour *variation* out of an image that has none.

What is missing is a node that derives colour from **luminance** rather than from the input's own hue, turning a brightness ramp into a colour ramp.

## Scope

**In scope:** one shader node that maps input value to a cosine palette, and a floating preview window for that palette, reachable from the Inspector through a capability other nodes can adopt later.

**Out of scope:** palette presets, colour pickers, importing shadertoy palettes, gradient editing by hand, and applying the palette to anything other than the input's value channel.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Colour source | **Palette replaces input hue** | The input serves purely as a luminance map. Identical result whether the input is grey or already coloured — the point is to colour something that has no colour |
| Luminance | **Input value is re-injected as brightness** | The palette supplies hue and saturation only. Relief survives colourisation; a palette that puts a bright colour at `v=0` would otherwise flatten or invert the image |
| Palette shape | **Cosine palette (Inigo Quilez)** | Oscillates rather than sweeping once, so it can band a smooth gradient. Richer than a two-colour duotone, and the standard formula behind most generative palettes |
| Control surface | **5 floats, not 12** | `a` and `b` fixed at 0.5 — the case nearly every published palette uses. Twelve numeric fields is unplayable during a set |
| Phase parameters | **Three separate floats, not one vec3** | Each becomes independently bindable to an audio feature. A vec3 would move all three channels together, which is exactly what you don't want |
| Preview location | **Free-floating non-modal window** | The node in the graph is untouched. Several previews can stay open side by side while you work elsewhere, including on a second screen |
| Preview discovery | **Capability declared on the node** | The Inspector asks whether a node offers a preview, not whether it is this particular node. Any future node opts in with one attribute |
| Preview persistence | **None — closed at load** | Purely transient UI state. Keeps the `.pn` format untouched, which has already cost silent parameter loss once |

## The shader

Five uniforms, all unprotected so they appear in the Inspector and in the audio-binding toolbox automatically:

| Uniform | Meaning |
|---|---|
| `frequency` | How many times the palette cycles across the luminance range |
| `phase_r`, `phase_g`, `phase_b` | Per-channel phase — this is what actually chooses the colours |
| `saturation` | Pulls the result back toward grey |

```glsl
float v = clamp(rgb2hsv(col).z, 0.0, 1.0);
vec3 pal = 0.5 + 0.5 * cos(6.28318 * (frequency * v + vec3(phase_r, phase_g, phase_b)));
vec3 pal_hsv = rgb2hsv(pal);
vec3 rgb = hsv2rgb(vec3(pal_hsv.x, pal_hsv.y * saturation, v));
```

The round trip through HSV is what enforces the luminance decision: only hue and saturation are taken from the palette, and `v` — the input's own value — is put back as brightness.

**`v` is clamped to `[0, 1]`, and this is load-bearing.** The FBOs are `f4` float targets (`program/colors/hsv_offset/hsv_offset.py:26`), so an upstream node — Bloom, Tone Mapping — can hand over channel values above 1 or below 0. `v` is used twice, and an out-of-range value corrupts both uses: it pushes the palette past the cycle count `frequency` asked for, so the colours no longer match what the preview shows, and it feeds `hsv2rgb` a brightness outside its domain. `hsv_offset.glsl:36` clamps its input for the same reason.

Clamping `v` rather than the incoming `col` is deliberate: clamping `col` per channel would shift the hue of out-of-range colours, which is harmless here only because the input hue is discarded anyway. Clamping the one value actually used says what is meant.

The Python `palette_rgb` used by the preview clamps identically, or the preview would disagree with the shader on exactly the HDR inputs where it matters most.

`rgb2hsv` / `hsv2rgb` are copied from `hsv_offset.glsl`, as every sibling in `program/colors/` already does. Factoring them into a shared include is a larger change to the shader-loading path and is not attempted here.

## File layout

Follows the template every node in `program/colors/` uses:

```
program/colors/value_gradient/
├── value_gradient.py      # ValueGradient(ProgramBase) + ValueGradientNode(ShaderNode, Colors)
├── value_gradient.glsl
└── palette_preview.py     # PalettePreviewWindow
```

Op code from `name_to_opcode("valuegradient")`. One input, one output, one FBO — structurally identical to `hsv_offset.py`.

## The preview capability

### Protocol on `ShaderNode`

```python
class ShaderNode(Node):
    preview_window_class = None          # subclasses opt in

    def setPreviewWindowVisible(self, visible): ...
    def isPreviewWindowVisible(self): ...
```

`ValueGradientNode` sets `preview_window_class = PalettePreviewWindow`. Nothing else declares anything.

**The node owns its window**, created lazily on first open and held on the instance. The Inspector cannot own it: selecting a different node rebuilds the whole Inspector panel (`clearLayout`, `gui/widgets/inspector_widget.py:199`), which would destroy or orphan the window every time the selection changed. Ownership on the node is also what allows several previews to stay open at once.

### Discovery in the Inspector

`updateInspector` passes the **node** (`gui/patanode.py:1011`), not the program, so the check sits naturally in `QDMInspector.updateParametersToSelectedItems` (`gui/widgets/inspector_widget.py:206`):

```python
if getattr(node, "preview_window_class", None) is not None:
    # add the "Palette preview" toggle
```

A node that declares nothing gets no toggle and an Inspector panel identical to today's. This is the whole extent of the generic change.

### What the window shows

- A horizontal gradient band, `v = 0` on the left to `v = 1` on the right, evaluated at ~32 stops.
- The current values of the five parameters, as text.

The values matter as much as the band: once a phase is bound to an audio feature it moves every frame, and seeing the number move is how you tell a modulated parameter from a stuck one.

### Refresh

The window refreshes on its own `QTimer` at ~20 Hz, re-reading the program's current uniform values each tick.

A timer rather than a signal: parameters change from at least two directions — Inspector edits and per-frame audio modulation — and only the audio path would be practical to hook. Polling captures both, and 20 Hz of evaluating a cosine at 32 points costs nothing next to the 60 Hz render already running.

### Palette evaluation lives in Python too

`palette_preview.py` holds a pure function mirroring the GLSL:

```python
def palette_rgb(t, frequency, phases, saturation) -> tuple  # 0..1 floats
```

This is the one genuinely testable piece of the feature, and the one place a bug would be invisible — a preview that disagrees with the shader is worse than no preview. It is a plain function so a test can compare it against values computed independently.

## Lifecycle and error handling

**Node deletion closes the window.** Handled in `ShaderNode.remove()`. Without it the window survives its node, with a timer polling a destroyed program — an orphaned window that raises every 50 ms.

**Default state is closed.** A freshly placed node has no window and no timer; nothing is created until the toggle is used.

**Nothing is serialized.** Reopening a scene never restores a preview window. The `.pn` format is unchanged by this feature.

## Testing

**Unit — no Qt, no GL:**

- `palette_rgb` — known inputs against independently computed values; `frequency = 0` gives a constant colour; `saturation = 0` gives grey; the function is periodic in phase.
- `palette_rgb` clamping — `t = 1.4` gives the same colour as `t = 1.0`, and `t = -0.2` the same as `t = 0.0`. This is the preview's half of the clamp; the shader's half is only reachable by eye.
- Inspector discovery — a node with `preview_window_class = None` produces no toggle; a node that declares one produces exactly one. Both asserted against the panel the Inspector actually builds, not against the attribute.

**Integration — `QApplication`, no GL context:**

- `setPreviewWindowVisible(True)` creates the window once and reuses it on a second call; `False` hides without destroying.
- Removing the node closes the window.

**Manual, required:**

- The shader itself. Feed a grayscale ramp, confirm the output is a gradient and that relief is preserved — dark stays dark. No unit test can judge this.
- Bind a phase to an audio feature and confirm the preview band tracks it live.

## Deferred by choice

Palette presets, a two-colour duotone mode, exposing `a` and `b`, and a curves display in the preview window. All are additive later; none are prerequisites.
