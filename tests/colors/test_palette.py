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


def test_current_params_prefer_the_bound_value_over_the_attribute(qapp):
    """Under an Inspector expression or an audio binding, the attribute and
    what the GPU received diverge -- the preview must show the latter or it
    misleads on exactly the setups worth previewing."""
    from program.colors.value_gradient.palette_preview import PalettePreviewWindow

    class FakeUniforms:
        last_values = {
            "": {
                "frequency": 4.0,
                "phase_r": 0.1,
                "phase_g": 0.2,
                "phase_b": 0.3,
                "saturation": 0.5,
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
        last_values = {"": {}}

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
