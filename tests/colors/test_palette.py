"""palette_rgb must agree with value_gradient.glsl exactly.

The preview exists so the five numbers can be judged by eye; a preview
that drifts from the shader defeats the whole point of the node.
"""

from program.colors.value_gradient.palette_preview import palette_rgb

PHASES = (0.0, 0.33, 0.67)


def previewWindowFor(frequency, phases, saturation):
    """A PalettePreviewWindow over a node that has never rendered, so
    currentParams falls back to the program attributes."""
    from program.colors.value_gradient.palette_preview import PalettePreviewWindow

    class FakeUniforms:
        last_values = {"": {}}

    class FakeProgram:
        programs_uniforms = FakeUniforms()

    FakeProgram.frequency = frequency
    FakeProgram.phase_r, FakeProgram.phase_g, FakeProgram.phase_b = phases
    FakeProgram.saturation = saturation

    class FakeNode:
        program = FakeProgram()

    return PalettePreviewWindow(FakeNode())


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


# --- Golden values, computed by hand from the GLSL ------------------------
#
# palette_c = 0.5 + 0.5*cos(2*pi*(frequency*t + phase_c))
# hue, sat  = rgb2hsv(palette).xy
# out       = clamp(hsv2rgb(hue, sat*saturation, t))
#
# These pin the function to the shader by value. The properties above are all
# self-consistency checks that a wrong-but-plausible implementation -- HLS
# instead of HSV, say -- would still satisfy.

GOLDEN = [
    # t=0.5, f=1, phases (0, 0.25, 0.5):
    #   palette = (0.5+0.5*cos(pi), 0.5+0.5*cos(1.5pi), 0.5+0.5*cos(2pi))
    #           = (0.0, 0.5, 1.0)
    #   max=1(blue) min=0 -> v=1, s=1, h=(4+(r-g)/delta)/6=(4-0.5)/6=0.5833333
    #   hsv2rgb(0.5833333, 1, 0.5): i=3 f=0.5 -> (p,q,v)
    #     p=0.5*(1-1)=0, q=0.5*(1-0.5)=0.25, v=0.5
    ((0.5, 1.0, (0.0, 0.25, 0.5), 1.0), (0.0, 0.25, 0.5)),
    # t=0.25, f=2, phases all 0:
    #   every channel = 0.5+0.5*cos(pi) = 0 -> palette black -> s=0
    #   hsv2rgb(h, 0, 0.25) = grey at the input value
    ((0.25, 2.0, (0.0, 0.0, 0.0), 1.0), (0.25, 0.25, 0.25)),
    # t=1, f=0.5, phases (0, 1/3, 2/3), saturation 0.5:
    #   palette = (0.5+0.5*cos(pi), 0.5+0.5*cos(300deg), 0.5+0.5*cos(420deg))
    #           = (0.0, 0.75, 0.75)
    #   max=0.75 min=0 -> v=0.75, s=1, h=0.5 (cyan)
    #   hsv2rgb(0.5, 1*0.5, 1.0): i=3 f=0 -> (p,q,v)
    #     p=1*(1-0.5)=0.5, q=1*(1-0)=1.0, v=1.0
    ((1.0, 0.5, (0.0, 1.0 / 3.0, 2.0 / 3.0), 0.5), (0.5, 1.0, 1.0)),
    # t=0.8, f=1, phases (0.1, 0.2, 0.4):
    #   palette = (0.5+0.5*cos(324deg), 0.5+0.5*cos(360deg), 0.5+0.5*cos(72deg))
    #           = (0.9045085, 1.0, 0.6545085)
    #   max=1(green) min=0.6545085 -> delta=0.3454915, v=1, s=0.3454915
    #   rc=0.0954915/0.3454915=0.2763932, gc=0, bc=1
    #   h=(2+rc-bc)/6=1.2763932/6=0.2127322
    #   hsv2rgb(0.2127322, 0.3454915, 0.8): i=1 f=0.2763932 -> (q,v,p)
    #     q=0.8*(1-0.3454915*0.2763932)=0.8*0.9045085=0.7236068
    #     p=0.8*(1-0.3454915)=0.8*0.6545085=0.5236068
    ((0.8, 1.0, (0.1, 0.2, 0.4), 1.0), (0.7236068, 0.8, 0.5236068)),
    # t=0.5, f=1, phases (0, 0.33, 0.67), saturation 2 -- the over-saturated
    #   case the output clamp exists for:
    #   palette = (0.0, 0.7408769, 0.7408769) -> v=0.7408769, s=1, h=0.5
    #   hsv2rgb(0.5, 1*2, 0.5): i=3 f=0 -> (p,q,v)
    #     p=0.5*(1-2)=-0.5, q=0.5*(1-0)=0.5, v=0.5
    #   clamped -> (0.0, 0.5, 0.5)
    ((0.5, 1.0, (0.0, 0.33, 0.67), 2.0), (0.0, 0.5, 0.5)),
]


def test_golden_values_match_the_glsl_formula():
    for (t, frequency, phases, saturation), expected in GOLDEN:
        actual = palette_rgb(t, frequency, phases, saturation)
        for channel, (a, e) in enumerate(zip(actual, expected)):
            assert (
                abs(a - e) < 1e-7
            ), "t=%s f=%s phases=%s sat=%s channel %d: got %r, expected %r" % (
                t,
                frequency,
                phases,
                saturation,
                channel,
                actual,
                expected,
            )


def test_over_saturation_stays_inside_the_unit_cube():
    """The shader extrapolates past full saturation and clamps the result --
    an Inspector expression of x*2 or an unbounded audio counter reaches
    here. Unclamped, colorsys returns negative components, QColor rejects
    them, and the preview shows nothing while the shader renders fine."""
    for saturation in (1.5, 2.0, 10.0):
        for step in range(11):
            rgb = palette_rgb(step / 10.0, 1.0, PHASES, saturation)
            assert all(
                0.0 <= channel <= 1.0 for channel in rgb
            ), "saturation %s at t=%s gave %r" % (saturation, step / 10.0, rgb)


def test_negative_saturation_stays_inside_the_unit_cube():
    for step in range(11):
        rgb = palette_rgb(step / 10.0, 1.0, PHASES, -1.0)
        assert all(0.0 <= channel <= 1.0 for channel in rgb)


def test_the_painted_band_shows_the_palette_under_over_saturation(qapp):
    """Renders the widget for real. Without the output clamp every stop is
    an invalid QColor, the gradient paints nothing, and the band comes out
    as the bare window background."""
    window = previewWindowFor(1.0, PHASES, 2.0)
    window.resize(360, 150)
    image = window.grab().toImage()

    # paintEvent's band is QRectF(12, 12, width-24, height-74).
    left, width = 12, window.width() - 24
    row_y = 40

    for t in (0.25, 0.5, 0.75):
        x = int(left + t * width)
        painted = image.pixelColor(x, row_y)
        expected = palette_rgb(t, 1.0, PHASES, 2.0)
        for got, want in zip(
            (painted.red(), painted.green(), painted.blue()), expected
        ):
            assert (
                abs(got - want * 255) <= 6
            ), "at t=%s the band painted (%d, %d, %d), the palette says %r" % (
                t,
                painted.red(),
                painted.green(),
                painted.blue(),
                expected,
            )


# --- Refresh timer lifecycle ----------------------------------------------


def test_the_timer_follows_visibility(qapp):
    """A hidden window has nothing to repaint, so it must not keep waking up
    every 50 ms -- previews accumulate as nodes are selected."""
    window = previewWindowFor(1.0, PHASES, 1.0)
    assert window._timer.isActive() is False

    window.show()
    assert window._timer.isActive() is True

    window.hide()
    assert window._timer.isActive() is False


def test_reopening_after_a_window_manager_close_restarts_the_timer(qapp):
    """Closing with the X button and re-ticking the Inspector box used to
    give back a permanently frozen window, which mid-performance reads as a
    stuck parameter."""
    from node.shader_node_base import ShaderNode
    from program.colors.value_gradient.palette_preview import PalettePreviewWindow

    class Node(ShaderNode):
        preview_window_class = PalettePreviewWindow

        def __init__(self):
            self._preview_window = None
            self.program = previewWindowFor(1.0, PHASES, 1.0).node.program

    node = Node()
    node.setPreviewWindowVisible(True)
    window = node._preview_window
    assert window._timer.isActive() is True

    window.close()
    assert window._timer.isActive() is False

    node.setPreviewWindowVisible(True)
    assert window._timer.isActive() is True
