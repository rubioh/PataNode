# Value Gradient Node Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `Value Gradient` shader node that turns a monotone image into a colour gradient by mapping its luminance through a cosine palette, with a floating palette preview reachable from the Inspector.

**Architecture:** The node follows the `program/colors/hsv_offset` template exactly — a `ProgramBase` subclass plus a `ShaderNode` subclass in one file, with its GLSL beside it. The preview is a separate free-floating window in the node's own folder, opened through a new generic capability on `ShaderNode` (`preview_window_class`) that the Inspector discovers. One line is added to `program_base.py` so any uniform records the value it actually bound, which is what makes the preview truthful under audio modulation.

**Tech Stack:** Python 3, PyQt5, moderngl, GLSL 330 core, pytest.

## Global Constraints

- Run everything through the project venv: `.venv/bin/python`, never `uv run`.
- Tests need offscreen Qt and the repo root on the path: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest`.
- numpy must stay below 2.3 — uniform binding breaks on 2.3+. Do not upgrade it.
- pre-commit runs black, isort and autoflake on commit. Let it reformat; do not fight it.
- Node folders under `program/colors/` have **no `__init__.py`** — they are namespace packages. Match the siblings.
- `name_to_opcode` is a plain sum of character ordinals, so names collide easily. `"valuegradient"` → **1387**, verified free against all 90 registered opcodes. Do not rename without re-checking.
- The full suite must stay green: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`.

---

## File Structure

| File | Responsibility |
|---|---|
| `program/colors/value_gradient/palette_preview.py` | `palette_rgb` (pure) + `PalettePreviewWindow` |
| `program/colors/value_gradient/value_gradient.glsl` | The fragment shader |
| `program/colors/value_gradient/value_gradient.py` | `ValueGradient(ProgramBase)` + `ValueGradientNode(ShaderNode, Colors)` |
| `program/colors/__init__.py` | One import line so the node registers |
| `node/shader_node_base.py` | The generic `preview_window_class` capability |
| `program/program_base.py` | One line recording each uniform's bound value |
| `gui/widgets/inspector_widget.py` | Discovery + the toggle |
| `tests/colors/` | New test package: `__init__.py`, `conftest.py`, and `test_palette.py`, `test_value_gradient_node.py`, `test_uniform_last_value.py`, `test_preview_capability.py`, `test_inspector_preview_toggle.py` |

---

### Task 1: The pure palette function

`palette_rgb` is the only genuinely testable piece of the colour maths, and the one place a bug hides: a preview that disagrees with the shader is worse than no preview.

**Files:**
- Create: `program/colors/value_gradient/palette_preview.py`
- Create: `tests/colors/__init__.py` (empty)
- Create: `tests/colors/conftest.py`
- Create: `tests/colors/test_palette.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `palette_rgb(t: float, frequency: float, phases: tuple, saturation: float) -> tuple[float, float, float]`, all components in `0..1`. `phases` is a 3-tuple `(phase_r, phase_g, phase_b)`.

- [ ] **Step 1: Create the test package files**

`tests/colors/__init__.py` — empty file.

`tests/colors/conftest.py`:

```python
"""Fixtures for colour node tests.

Mirrors tests/session/conftest.py: anything touching a QWidget needs a
live QApplication, and pytest gives each test package its own conftest.
"""

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
```

- [ ] **Step 2: Write the failing tests**

`tests/colors/test_palette.py`:

```python
"""palette_rgb must agree with value_gradient.glsl exactly.

The preview exists so the five numbers can be judged by eye; a preview
that drifts from the shader defeats the whole point of the node.
"""

from program.colors.value_gradient.palette_preview import palette_rgb

PHASES = (0.0, 0.33, 0.67)


def test_black_input_stays_black():
    """The input value is re-injected as brightness, so v=0 is black no
    matter what colour the palette produces there."""
    assert palette_rgb(0.0, 1.0, PHASES, 1.0) == (0.0, 0.0, 0.0)


def test_zero_saturation_gives_grey_at_the_input_value():
    r, g, b = palette_rgb(0.6, 1.0, PHASES, 0.0)
    assert r == g == b
    assert abs(r - 0.6) < 1e-9


def test_frequency_zero_holds_one_hue_across_the_range():
    """With no cycling the palette is constant, so two different inputs
    differ only in brightness -- their ratios stay identical."""
    dark = palette_rgb(0.3, 0.0, PHASES, 1.0)
    bright = palette_rgb(0.9, 0.0, PHASES, 1.0)
    for d, b in zip(dark, bright):
        assert abs(d * 3.0 - b) < 1e-9


def test_phase_is_periodic():
    """cos has period 1 in phase, so adding a whole turn changes nothing."""
    base = palette_rgb(0.5, 1.0, (0.1, 0.2, 0.3), 1.0)
    shifted = palette_rgb(0.5, 1.0, (1.1, 2.2, -0.7), 1.0)
    for a, b in zip(base, shifted):
        assert abs(a - b) < 1e-9


def test_input_above_one_is_clamped():
    """FBOs are f4 float targets, so Bloom upstream can hand over values
    past 1. Unclamped they would push the palette past the cycle count
    frequency asked for AND overdrive the output brightness."""
    assert palette_rgb(1.4, 2.0, PHASES, 1.0) == palette_rgb(1.0, 2.0, PHASES, 1.0)


def test_negative_input_is_clamped():
    assert palette_rgb(-0.2, 2.0, PHASES, 1.0) == palette_rgb(0.0, 2.0, PHASES, 1.0)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/test_palette.py -q`

Expected: collection error — `ModuleNotFoundError: No module named 'program.colors.value_gradient'`.

- [ ] **Step 4: Write the minimal implementation**

`program/colors/value_gradient/palette_preview.py`:

```python
"""Palette evaluation and the floating preview window for Value Gradient."""

import colorsys
import math

TWO_PI = 2.0 * math.pi


def palette_rgb(t, frequency, phases, saturation):
    """Cosine palette, mirroring value_gradient.glsl exactly.

    `t` is the input value and is clamped to [0, 1] here for the same
    reason the shader clamps it: the FBOs are f4 float targets, so an
    upstream node can deliver out-of-range channels, and `t` is used
    twice -- once to index the palette, once as the output brightness.

    The palette supplies hue and saturation only; `t` comes back as
    brightness so the input's relief survives colourisation.
    """
    t = min(1.0, max(0.0, t))
    palette = [0.5 + 0.5 * math.cos(TWO_PI * (frequency * t + phase)) for phase in phases]
    hue, sat, _ = colorsys.rgb_to_hsv(*palette)
    return colorsys.hsv_to_rgb(hue, sat * saturation, t)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/test_palette.py -q`

Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add program/colors/value_gradient/palette_preview.py tests/colors/
git commit -m "feat(colors): add the cosine palette evaluation for Value Gradient"
```

---

### Task 2: The shader, the program and the node

**Files:**
- Create: `program/colors/value_gradient/value_gradient.glsl`
- Create: `program/colors/value_gradient/value_gradient.py`
- Modify: `program/colors/__init__.py`
- Create: `tests/colors/test_value_gradient_node.py`

**Interfaces:**
- Consumes: nothing from Task 1 yet.
- Produces: `OP_CODE_VALUEGRADIENT` (int, 1387), `ValueGradient(ProgramBase)`, `ValueGradientNode(ShaderNode, Colors)` with `op_title = "Value Gradient"`. Program attributes: `frequency`, `phase_r`, `phase_g`, `phase_b`, `saturation`, `iChannel0`.

- [ ] **Step 1: Write the failing tests**

`tests/colors/test_value_gradient_node.py`:

```python
"""The GLSL cannot be unit-tested -- it needs a GL context and human eyes.

What is checked here is everything around it that can silently rot: that
the node registers, that its opcode has not drifted into a collision, and
that the shader still declares the contract the Python side assumes.
"""

from os.path import dirname, join

import program.program_conf  # noqa: F401  (registers every node; see tests/serialization)
from node.node_conf import SHADER_NODES
from program.colors.value_gradient import value_gradient as value_gradient_module
from program.colors.value_gradient.value_gradient import (
    OP_CODE_VALUEGRADIENT,
    ValueGradientNode,
)

GLSL = join(dirname(value_gradient_module.__file__), "value_gradient.glsl")


def test_the_node_is_registered_under_its_opcode():
    assert SHADER_NODES[OP_CODE_VALUEGRADIENT] is ValueGradientNode


def test_the_opcode_is_the_expected_value():
    """name_to_opcode is a sum of ordinals, so any rename silently moves
    the opcode -- and a moved opcode breaks every saved scene using it."""
    assert OP_CODE_VALUEGRADIENT == 1387


def test_the_shader_declares_the_five_controls():
    source = open(GLSL).read()
    for uniform in ("frequency", "phase_r", "phase_g", "phase_b", "saturation"):
        assert "uniform float %s;" % uniform in source


def test_the_shader_clamps_the_value():
    """The value indexes the palette and sets the output brightness. An
    f4 input above 1 corrupts both, so the clamp is load-bearing rather
    than defensive."""
    source = open(GLSL).read()
    assert "clamp(rgb2hsv(col).z, 0.0, 1.0)" in source
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/test_value_gradient_node.py -q`

Expected: collection error — `ModuleNotFoundError: No module named 'program.colors.value_gradient.value_gradient'`.

- [ ] **Step 3: Write the shader**

`program/colors/value_gradient/value_gradient.glsl`:

```glsl
#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float frequency;
uniform float phase_r;
uniform float phase_g;
uniform float phase_b;
uniform float saturation;

#define R iResolution

vec3 rgb2hsv(vec3 c)
{
    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));

    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c)
{
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main()
{
    vec2 uv = gl_FragCoord.xy;
    vec3 col = texture(iChannel0, uv / R).rgb;

    // Clamped because the FBOs are f4: an upstream Bloom or Tone Mapping
    // can deliver channels outside [0,1], and this value is used twice --
    // to index the palette and as the output brightness.
    float v = clamp(rgb2hsv(col).z, 0.0, 1.0);

    vec3 palette = 0.5 + 0.5 * cos(6.28318530718 *
        (frequency * v + vec3(phase_r, phase_g, phase_b)));

    // Only hue and saturation come from the palette; v goes back in as
    // brightness so the input's relief survives.
    vec3 palette_hsv = rgb2hsv(palette);
    vec3 rgb = hsv2rgb(vec3(palette_hsv.x, palette_hsv.y * saturation, v));

    fragColor = vec4(clamp(rgb, vec3(0.), vec3(1.)), 1.0);
}
```

- [ ] **Step 4: Write the program and node**

`program/colors/value_gradient/value_gradient.py`:

```python
from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import Colors, ShaderNode
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, name_to_opcode, register_program


OP_CODE_VALUEGRADIENT = name_to_opcode("valuegradient")


@register_program(OP_CODE_VALUEGRADIENT)
class ValueGradient(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Value Gradient"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, "f4"],
        ]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "value_gradient.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 1
        # One full turn of the palette across the luminance range.
        self.frequency = 1.0
        # Evenly spread phases -- the classic rainbow starting point.
        self.phase_r = 0.0
        self.phase_g = 0.33
        self.phase_b = 0.67
        self.saturation = 1.0

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "iChannel0": "iChannel0",
            "frequency": "frequency",
            "phase_r": "phase_r",
            "phase_g": "phase_g",
            "phase_b": "phase_b",
            "saturation": "saturation",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def updateParams(self, af):
        if af is None:
            return

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)

        textures[0].use(1)

        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_VALUEGRADIENT)
class ValueGradientNode(ShaderNode, Colors):
    op_title = "Value Gradient"
    op_code = OP_CODE_VALUEGRADIENT
    content_label = ""
    content_label_objname = "shader_value_gradient"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = ValueGradient(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            return self.program.norender()

        input_nodes = self.getShaderInputs()

        if not len(input_nodes):
            return self.program.norender()

        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
```

- [ ] **Step 5: Register the module**

Add to `program/colors/__init__.py`, keeping the existing alphabetical order (after `tone_mapping`):

```python
from program.colors.value_gradient import value_gradient
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/ -q`

Expected: `10 passed`.

- [ ] **Step 7: Run the full suite**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`

Expected: all green. A failure here almost certainly means an opcode collision — re-check Global Constraints.

- [ ] **Step 8: Commit**

```bash
git add program/colors/value_gradient/ program/colors/__init__.py tests/colors/
git commit -m "feat(colors): add the Value Gradient node and shader"
```

---

### Task 3: Record each uniform's bound value

The preview must show what the shader actually receives. The effective value is computed inside `bindUniformToProgram` — it is the program attribute *or* an audio feature, with the Inspector's expression applied on top (`program/program_base.py:714-725`). Reading the raw attribute would lie the moment a phase is bound to a kick.

**Files:**
- Modify: `program/program_base.py:714-725`
- Create: `tests/colors/test_uniform_last_value.py`

**Interfaces:**
- Produces: `program.programs_uniforms.uniforms[program_name][uniform_name]["last_value"]` — the float last sent to the GPU for that uniform. Absent until the first bind.

- [ ] **Step 1: Write the failing test**

`tests/colors/test_uniform_last_value.py`:

```python
"""The preview reads the value the shader actually got, not the program
attribute -- those differ whenever an Inspector expression or an audio
binding sits in between.
"""


def test_bound_value_is_recorded_on_the_uniform_info():
    """ProgramsUniforms is at program/program_base.py:583; the bind loop
    ends with `program[uniform_name] = modified_data`, so a plain dict
    stands in for the moderngl program."""
    from program.program_base import ProgramsUniforms

    holder = ProgramsUniforms.__new__(ProgramsUniforms)
    info = {"param_name": "frequency", "type": "attribute"}
    holder.uniforms = {"": {"frequency": info}}
    holder.protected = []
    holder.programs = {"": {}}

    class FakeParent:
        frequency = 2.5

        def getAdaptableEvaluationForUniform(self, program_name, uniform_name, data):
            # Stands in for an Inspector expression of "x*2".
            return data * 2

    holder.parent = FakeParent()

    holder.bindUniformToProgram(None, program_name="")

    assert info["last_value"] == 5.0, (
        "the recorded value must be the one after expression evaluation, "
        "not the raw program attribute"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/test_uniform_last_value.py -q`

Expected: `KeyError: 'last_value'`.

- [ ] **Step 3: Add the recording line**

In `program/program_base.py`, immediately after `modified_data` is computed in `bindUniformToProgram`:

```python
                    modified_data = self.parent.getAdaptableEvaluationForUniform(
                        program_name + "program", uniform_name, data
                    )

                    # What the GPU actually receives, kept so preview widgets
                    # can show the effective value rather than the raw
                    # attribute -- the two differ under an Inspector
                    # expression or an audio binding.
                    info["last_value"] = modified_data
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/test_uniform_last_value.py -q`

Expected: `1 passed`.

- [ ] **Step 5: Run the full suite**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`

Expected: all green. This touches core rendering, so a regression here matters more than anywhere else in this plan.

- [ ] **Step 6: Commit**

```bash
git add program/program_base.py tests/colors/test_uniform_last_value.py
git commit -m "feat(program): record each uniform's bound value for preview widgets"
```

---

### Task 4: The preview capability on ShaderNode

Generic, so the Inspector never learns about Value Gradient specifically.

**Files:**
- Modify: `node/shader_node_base.py` (the `ShaderNode` class, from line 74)
- Create: `tests/colors/test_preview_capability.py`

**Interfaces:**
- Produces, on `ShaderNode`: class attribute `preview_window_class = None`; instance attribute `_preview_window`; methods `setPreviewWindowVisible(visible: bool)`, `isPreviewWindowVisible() -> bool`, `closePreviewWindow()`, and an overridden `remove()`.
- The window class is constructed as `preview_window_class(node)`.

- [ ] **Step 1: Write the failing tests**

`tests/colors/test_preview_capability.py`:

```python
"""The preview window is owned by the node, not the Inspector.

Selecting another node runs QDMInspector.clearLayout (inspector_widget.py:199),
which deletes the whole panel -- an Inspector-owned window would be orphaned
on every selection change, and several previews could not stay open at once.
"""

import pytest
from PyQt5.QtWidgets import QWidget

from node.shader_node_base import ShaderNode


class DummyWindow(QWidget):
    def __init__(self, node):
        super().__init__()
        self.node = node


class PreviewNode(ShaderNode):
    """A ShaderNode with the capability but without ShaderNode.__init__,
    which builds a GL program and needs a live context."""

    preview_window_class = DummyWindow

    def __init__(self):
        self._preview_window = None


class PlainNode(ShaderNode):
    def __init__(self):
        self._preview_window = None


def test_a_node_without_the_capability_opens_nothing(qapp):
    node = PlainNode()
    node.setPreviewWindowVisible(True)
    assert node.isPreviewWindowVisible() is False


def test_showing_creates_the_window(qapp):
    node = PreviewNode()
    node.setPreviewWindowVisible(True)
    assert node.isPreviewWindowVisible() is True


def test_the_window_is_created_once_and_reused(qapp):
    """Re-opening must not leave a trail of orphaned windows behind."""
    node = PreviewNode()
    node.setPreviewWindowVisible(True)
    first = node._preview_window
    node.setPreviewWindowVisible(False)
    node.setPreviewWindowVisible(True)
    assert node._preview_window is first


def test_hiding_does_not_destroy_the_window(qapp):
    node = PreviewNode()
    node.setPreviewWindowVisible(True)
    node.setPreviewWindowVisible(False)
    assert node._preview_window is not None
    assert node.isPreviewWindowVisible() is False


def test_removing_the_node_closes_its_window(qapp, monkeypatch):
    """Otherwise the window outlives its node, with a timer polling a
    program that no longer exists."""
    from nodeeditor.node_node import Node

    monkeypatch.setattr(Node, "remove", lambda self: None)

    node = PreviewNode()
    node.setPreviewWindowVisible(True)
    window = node._preview_window

    node.remove()

    assert window.isVisible() is False
    assert node._preview_window is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/test_preview_capability.py -q`

Expected: `AttributeError: 'PlainNode' object has no attribute 'setPreviewWindowVisible'`.

- [ ] **Step 3: Add the capability**

In `node/shader_node_base.py`, add the class attribute alongside the existing ones on `ShaderNode` (near `content_label_objname`, line 79):

```python
    # Subclasses opt into a floating preview by naming a QWidget class here.
    # The Inspector discovers the capability from this attribute alone.
    preview_window_class = None
```

Add `self._preview_window = None` in `ShaderNode.__init__`, next to `self.program = None` (line 89).

Add the methods to `ShaderNode`:

```python
    def setPreviewWindowVisible(self, visible):
        """Open or hide this node's preview window.

        The node owns the window rather than the Inspector: selecting a
        different node rebuilds the entire Inspector panel, which would
        orphan an Inspector-owned window every time.
        """
        if self.preview_window_class is None:
            return

        if visible:
            if self._preview_window is None:
                self._preview_window = self.preview_window_class(self)
            self._preview_window.show()
            self._preview_window.raise_()
        elif self._preview_window is not None:
            self._preview_window.hide()

    def isPreviewWindowVisible(self):
        return self._preview_window is not None and self._preview_window.isVisible()

    def closePreviewWindow(self):
        if self._preview_window is not None:
            self._preview_window.close()
            self._preview_window = None

    def remove(self):
        # Before super(), which tears down the node the window points at.
        self.closePreviewWindow()
        super().remove()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/test_preview_capability.py -q`

Expected: `5 passed`.

- [ ] **Step 5: Check the tests guard the production lines**

Delete the `self.closePreviewWindow()` line from `remove()`, re-run the file, confirm `test_removing_the_node_closes_its_window` fails, then restore it. A test that stays green when its line is deleted is not a test.

- [ ] **Step 6: Run the full suite**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add node/shader_node_base.py tests/colors/test_preview_capability.py
git commit -m "feat(node): add an opt-in preview window capability to ShaderNode"
```

---

### Task 5: The palette preview window

**Files:**
- Modify: `program/colors/value_gradient/palette_preview.py`
- Modify: `program/colors/value_gradient/value_gradient.py`
- Modify: `tests/colors/test_palette.py` (append)

**Interfaces:**
- Consumes: `palette_rgb` (Task 1), `last_value` (Task 3), `preview_window_class` (Task 4).
- Produces: `PalettePreviewWindow(node)` — a free-floating `QWidget`; `PalettePreviewWindow.currentParams() -> (frequency, (phase_r, phase_g, phase_b), saturation)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/colors/test_palette.py`:

```python
def test_current_params_prefer_the_bound_value_over_the_attribute(qapp):
    """Under an Inspector expression or an audio binding, the attribute and
    what the GPU received diverge -- the preview must show the latter or it
    misleads on exactly the setups worth previewing."""
    from program.colors.value_gradient.palette_preview import PalettePreviewWindow

    class FakeUniforms:
        uniforms = {
            "": {
                "frequency": {"last_value": 4.0},
                "phase_r": {"last_value": 0.1},
                "phase_g": {"last_value": 0.2},
                "phase_b": {"last_value": 0.3},
                "saturation": {"last_value": 0.5},
            }
        }

    class FakeProgram:
        programs_uniforms = FakeUniforms()
        frequency = 1.0
        phase_r = 0.0
        phase_g = 0.33
        phase_b = 0.67
        saturation = 1.0

    class FakeNode:
        program = FakeProgram()

    window = PalettePreviewWindow(FakeNode())
    assert window.currentParams() == (4.0, (0.1, 0.2, 0.3), 0.5)


def test_current_params_fall_back_to_attributes_before_the_first_render(qapp):
    """A node that has never rendered has no last_value yet, and the window
    can be opened immediately after dropping the node."""
    from program.colors.value_gradient.palette_preview import PalettePreviewWindow

    class FakeUniforms:
        uniforms = {"": {}}

    class FakeProgram:
        programs_uniforms = FakeUniforms()
        frequency = 1.0
        phase_r = 0.0
        phase_g = 0.33
        phase_b = 0.67
        saturation = 1.0

    class FakeNode:
        program = FakeProgram()

    window = PalettePreviewWindow(FakeNode())
    assert window.currentParams() == (1.0, (0.0, 0.33, 0.67), 1.0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/test_palette.py -q`

Expected: `ImportError: cannot import name 'PalettePreviewWindow'`.

- [ ] **Step 3: Implement the window**

Append to `program/colors/value_gradient/palette_preview.py`:

```python
from PyQt5.QtCore import QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QLinearGradient, QPainter
from PyQt5.QtWidgets import QWidget

PARAM_NAMES = ("frequency", "phase_r", "phase_g", "phase_b", "saturation")
GRADIENT_STOPS = 32
REFRESH_MS = 50


class PalettePreviewWindow(QWidget):
    """Free-floating live preview of one Value Gradient node's palette.

    Refreshed by a timer rather than a signal: the parameters move from two
    directions -- Inspector edits and per-frame audio modulation -- and only
    the second would be practical to hook. Polling catches both, and
    evaluating a cosine 32 times at 20 Hz costs nothing beside the 60 Hz
    render already running.
    """

    def __init__(self, node):
        super().__init__()
        self.node = node
        self.setWindowTitle("Palette — %s" % getattr(node, "title", "Value Gradient"))
        self.resize(360, 150)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(REFRESH_MS)

    def currentParams(self):
        """The values the shader actually received, falling back to the
        program attributes before the node has ever rendered."""
        program = self.node.program
        uniforms = program.programs_uniforms.uniforms.get("", {})

        values = []
        for name in PARAM_NAMES:
            info = uniforms.get(name, {})
            if "last_value" in info:
                values.append(float(info["last_value"]))
            else:
                values.append(float(getattr(program, name)))

        frequency, phase_r, phase_g, phase_b, saturation = values
        return frequency, (phase_r, phase_g, phase_b), saturation

    def paintEvent(self, event):
        frequency, phases, saturation = self.currentParams()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        band = QRectF(12, 12, self.width() - 24, self.height() - 74)
        gradient = QLinearGradient(band.topLeft(), band.topRight())
        for step in range(GRADIENT_STOPS + 1):
            t = step / GRADIENT_STOPS
            r, g, b = palette_rgb(t, frequency, phases, saturation)
            gradient.setColorAt(
                t, QColor(int(r * 255), int(g * 255), int(b * 255))
            )
        painter.fillRect(band, gradient)

        painter.setPen(QColor(200, 200, 200))
        text = "frequency %.3f\nphase  %.3f  %.3f  %.3f\nsaturation %.3f" % (
            frequency, phases[0], phases[1], phases[2], saturation
        )
        painter.drawText(
            QRectF(12, band.bottom() + 8, self.width() - 24, 60),
            Qt.AlignLeft | Qt.AlignTop,
            text,
        )
        painter.end()

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
```

- [ ] **Step 4: Declare the capability on the node**

In `program/colors/value_gradient/value_gradient.py`, add the import at the top:

```python
from program.colors.value_gradient.palette_preview import PalettePreviewWindow
```

and the attribute on `ValueGradientNode`, beside `content_label_objname`:

```python
    preview_window_class = PalettePreviewWindow
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/ -q`

Expected: all green.

- [ ] **Step 6: Run the full suite**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add program/colors/value_gradient/ tests/colors/test_palette.py
git commit -m "feat(colors): add the floating palette preview window"
```

---

### Task 6: Inspector discovery and the toggle

**Files:**
- Modify: `gui/widgets/inspector_widget.py:206-218`
- Create: `tests/colors/test_inspector_preview_toggle.py`

**Interfaces:**
- Consumes: `preview_window_class`, `setPreviewWindowVisible`, `isPreviewWindowVisible` (Task 4).
- Produces: `QDMInspector.createPreviewToggle(node) -> QGroupBox`, called from `updateParametersToSelectedItems` only when the node declares a preview class.

- [ ] **Step 1: Write the failing tests**

`tests/colors/test_inspector_preview_toggle.py`:

```python
"""The Inspector asks whether a node offers a preview -- it never learns
which node that is. Any future node inherits the toggle by declaring
preview_window_class.
"""

from PyQt5.QtWidgets import QCheckBox, QWidget

from gui.widgets.inspector_widget import QDMInspector


class DummyWindow(QWidget):
    def __init__(self, node):
        super().__init__()


class FakeNode:
    preview_window_class = None

    def __init__(self):
        self.visible = False

    def setPreviewWindowVisible(self, visible):
        self.visible = visible

    def isPreviewWindowVisible(self):
        return self.visible


class PreviewNode(FakeNode):
    preview_window_class = DummyWindow


def checkboxes(widget):
    return widget.findChildren(QCheckBox)


def test_a_node_without_a_preview_gets_no_toggle(qapp):
    inspector = QDMInspector()
    assert inspector.createPreviewToggle(FakeNode()) is None


def test_a_node_with_a_preview_gets_one_toggle(qapp):
    inspector = QDMInspector()
    box = inspector.createPreviewToggle(PreviewNode())
    assert box is not None
    assert len(checkboxes(box)) == 1


def test_ticking_the_toggle_opens_the_preview(qapp):
    inspector = QDMInspector()
    node = PreviewNode()
    box = inspector.createPreviewToggle(node)

    checkboxes(box)[0].setChecked(True)

    assert node.visible is True


def test_unticking_the_toggle_hides_the_preview(qapp):
    inspector = QDMInspector()
    node = PreviewNode()
    node.visible = True
    box = inspector.createPreviewToggle(node)

    checkboxes(box)[0].setChecked(True)
    checkboxes(box)[0].setChecked(False)

    assert node.visible is False


def test_the_toggle_reflects_a_window_already_open(qapp):
    """Re-selecting a node whose preview is open must not show an unticked
    box beside a visible window."""
    inspector = QDMInspector()
    node = PreviewNode()
    node.visible = True

    box = inspector.createPreviewToggle(node)

    assert checkboxes(box)[0].isChecked() is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/test_inspector_preview_toggle.py -q`

Expected: `AttributeError: 'QDMInspector' object has no attribute 'createPreviewToggle'`.

- [ ] **Step 3: Implement the toggle**

Add to `QDMInspector` in `gui/widgets/inspector_widget.py`:

```python
    def createPreviewToggle(self, node):
        """A checkbox for nodes that offer a floating preview, None otherwise.

        Discovery is by declared capability, not by node type: a node opts
        in with preview_window_class and the Inspector needs no knowledge of
        which node it is.
        """
        if getattr(node, "preview_window_class", None) is None:
            return None

        groupBox = QGroupBox("")
        checkbox = QCheckBox("Palette preview")
        # A window left open stays open when you reselect the node, so the
        # box must start from the node's real state, not from unchecked.
        checkbox.setChecked(node.isPreviewWindowVisible())
        checkbox.toggled.connect(node.setPreviewWindowVisible)

        vbox = QVBoxLayout()
        vbox.addWidget(checkbox)
        groupBox.setLayout(vbox)
        groupBox.setFlat(True)
        return groupBox
```

- [ ] **Step 4: Call it from the panel builder**

In `updateParametersToSelectedItems`, after `self.createSetWinSizeToolbox(obj)`:

```python
        preview_toggle = self.createPreviewToggle(obj)
        if preview_toggle is not None:
            self.grid.addWidget(preview_toggle)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/colors/test_inspector_preview_toggle.py -q`

Expected: `5 passed`.

- [ ] **Step 6: Check the call site is guarded**

Delete the three lines added in Step 4, run the whole `tests/colors/` directory, and observe that everything still passes — the unit tests cover `createPreviewToggle` but not its call site. Restore the lines, then add this test to `tests/colors/test_inspector_preview_toggle.py` so the call site is guarded too:

```python
def test_the_panel_builder_adds_the_toggle(qapp, monkeypatch):
    """createPreviewToggle can be perfect and still never be called."""
    inspector = QDMInspector()
    calls = []
    monkeypatch.setattr(
        inspector, "createSetWinSizeToolbox", lambda obj: None
    )
    monkeypatch.setattr(
        inspector, "createGpuParametersToolbox", lambda info: None
    )
    monkeypatch.setattr(
        inspector, "createCpuParametersToolbox", lambda info: None
    )
    monkeypatch.setattr(inspector, "createUniformsToolbox", lambda binding: None)
    monkeypatch.setattr(
        inspector,
        "createPreviewToggle",
        lambda node: calls.append(node) or None,
    )

    class Obj:
        def getUniformsBinding(self):
            return {}

        def getGpuAdaptableParameters(self):
            return {}

        def getCpuAdaptableParameters(self):
            return {}

    obj = Obj()
    inspector.updateParametersToSelectedItems(obj)

    assert calls == [obj]
```

Re-run the file and confirm `6 passed`, then delete the Step 4 lines once more to confirm this new test fails, and restore them.

- [ ] **Step 7: Run the full suite**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add gui/widgets/inspector_widget.py tests/colors/test_inspector_preview_toggle.py
git commit -m "feat(inspector): discover and toggle node preview windows"
```

---

## Manual verification

None of the following can be unit-tested; all of it needs the app and human eyes.

- [ ] Launch: `.venv/bin/python main.py`
- [ ] Drop a `Value Gradient` from the Colors category, feed it a grayscale or single-hue source, wire it to a Screen node.
- [ ] Confirm the output is a colour gradient and that **relief is preserved** — dark areas stay dark. This is the decision the whole design rests on.
- [ ] Feed it a source with Bloom upstream (values above 1). Confirm no blown-out or wrapped colours — this is the clamp doing its job.
- [ ] Select the node, tick `Palette preview`, confirm the window opens and the band matches what is on screen.
- [ ] Change `frequency` in the Inspector, confirm the band and the printed value both follow.
- [ ] Bind `phase_r` to `kick_count`, confirm the band and the printed value move on the beat — this is what the `last_value` recording exists for.
- [ ] Select a different node, confirm the preview window stays open and the toggle disappears from the panel.
- [ ] Reselect the Value Gradient node, confirm the toggle reappears **already ticked**.
- [ ] Delete the node, confirm the window closes.
- [ ] Save the scene, reopen it, confirm no preview window appears.
