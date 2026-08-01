"""Tests for the DepthSmooth program on a real GL context.

Feeds the program hand-built depth images (normalised depth in rgb, validity in
a) and renders repeatedly, so the assertions are about what the smoothing
actually converges to rather than about the shader source.
"""

import moderngl
import numpy as np
import pytest

from program.depth.depth_smooth.depth_smooth import (
    DEFAULT_HOLD_FRAMES,
    DEFAULT_SMOOTH_RATE,
    DepthSmooth,
)

WIN_SIZE = (16, 16)

EXPECTED_UNIFORMS = {
    "iResolution",
    "input_texture",
    "history",
    "smooth_rate",
    "hold_frames",
}

PROTECTED_UNIFORMS = {"input_texture", "history"}


@pytest.fixture(scope="module")
def ctx():
    try:
        context = moderngl.create_standalone_context()
    except Exception as error:
        pytest.skip(f"no usable GL context: {error}")
    yield context
    context.release()


def make_program(ctx):
    program = DepthSmooth(ctx=ctx, win_size=WIN_SIZE)
    program.connectFbos(
        [
            ctx.framebuffer(color_attachments=[ctx.texture(WIN_SIZE, 4, dtype="f4")])
            for _ in range(program.required_fbos)
        ]
    )
    return program


def depth_image(ctx, depth, valid=True):
    """A uniform depth image in the format Depth Input produces."""
    pixel = [depth, depth, depth, 1.0 if valid else 0.0]
    data = np.tile(np.array(pixel, dtype="f4"), (WIN_SIZE[1], WIN_SIZE[0], 1))
    return ctx.texture(WIN_SIZE, 4, data.tobytes(), dtype="f4")


def read(program):
    """The rgba of the pixel the program last wrote."""
    texture = program.norender()
    fbo = [f for f in program.fbos if f.color_attachments[0] is texture][0]
    pixels = np.frombuffer(fbo.read(components=4, dtype="f4"), dtype="f4")
    return pixels.reshape((WIN_SIZE[1], WIN_SIZE[0], 4))[0, 0]


def test_the_shader_registers_exactly_the_declared_uniforms(ctx):
    program = make_program(ctx)

    parsed = set(program.programs_uniforms.uniforms[""].keys())

    # Equality: an extra entry is a phantom uniform, and those get serialised
    # into .pn scene files.
    assert parsed == EXPECTED_UNIFORMS


def test_sampler_uniforms_get_no_inspector_entry(ctx):
    program = make_program(ctx)

    exposed = set(program.adaptable_parameters_dict["program"].keys())

    assert exposed == {"smooth_rate", "hold_frames"}
    assert not exposed & PROTECTED_UNIFORMS


def test_a_rate_of_one_passes_the_input_straight_through(ctx):
    program = make_program(ctx)
    program.smooth_rate = 1.0

    # Changing the input between renders is what makes this meaningful: with a
    # constant image it would pass even if rate were ignored entirely and the
    # shader always adopted the current frame.
    program.render([depth_image(ctx, 0.2)])
    program.render([depth_image(ctx, 0.8)])

    assert read(program)[0] == pytest.approx(0.8, abs=1e-5)


def test_one_nan_frame_does_not_poison_the_pixel_forever(ctx):
    # NaN is absorbing without a guard: mix() propagates it and the hold branch
    # preserves it, so the pixel would stay NaN until the buffers were cleared.
    program = make_program(ctx)
    program.smooth_rate = 0.5

    program.render([depth_image(ctx, float("nan"))])
    for _ in range(3):
        program.render([depth_image(ctx, 0.5)])

    recovered = read(program)[0]
    assert not np.isnan(recovered)
    assert recovered == pytest.approx(0.5, abs=1e-5)


def test_the_first_valid_frame_is_adopted_outright(ctx):
    # Fading in from an empty history would darken every newly measured
    # surface for several frames.
    program = make_program(ctx)
    program.smooth_rate = 0.25

    program.render([depth_image(ctx, 0.8)])

    assert read(program)[0] == pytest.approx(0.8, abs=1e-5)


def test_a_change_converges_gradually_rather_than_jumping(ctx):
    program = make_program(ctx)
    program.smooth_rate = 0.5

    program.render([depth_image(ctx, 0.0)])
    program.render([depth_image(ctx, 1.0)])
    after_one = read(program)[0]
    program.render([depth_image(ctx, 1.0)])
    after_two = read(program)[0]

    # mix(0, 1, 0.5) then mix(0.5, 1, 0.5): halfway, then three quarters.
    assert after_one == pytest.approx(0.5, abs=1e-5)
    assert after_two == pytest.approx(0.75, abs=1e-5)
    # Strictly monotonic towards the target, which is what "smooth" means here.
    assert after_one < after_two < 1.0


def test_an_unmeasured_pixel_holds_its_last_depth(ctx):
    program = make_program(ctx)
    program.smooth_rate = 0.5
    program.hold_frames = 10.0

    program.render([depth_image(ctx, 0.6)])
    program.render([depth_image(ctx, 0.0, valid=False)])
    held = read(program)

    # The depth survives, and alpha has decayed by exactly one step.
    assert held[0] == pytest.approx(0.6, abs=1e-5)
    assert held[3] == pytest.approx(0.9, abs=1e-5)


def test_a_hole_fades_to_invalid_after_hold_frames(ctx):
    program = make_program(ctx)
    program.hold_frames = 4.0
    invalid = depth_image(ctx, 0.0, valid=False)

    program.render([depth_image(ctx, 0.6)])
    for _ in range(4):
        program.render([invalid])

    # Freshness reaches zero, so downstream sees a hole again rather than a
    # value held forever.
    assert read(program)[3] == pytest.approx(0.0, abs=1e-5)


def test_a_returning_measurement_restores_full_freshness(ctx):
    program = make_program(ctx)
    program.hold_frames = 10.0

    program.render([depth_image(ctx, 0.6)])
    program.render([depth_image(ctx, 0.0, valid=False)])
    program.render([depth_image(ctx, 0.6)])

    assert read(program)[3] == pytest.approx(1.0, abs=1e-5)


def test_the_buffers_swap_so_history_survives_between_frames(ctx):
    # The whole design rests on this: each render must read the buffer the
    # previous render wrote, never the one it is writing.
    program = make_program(ctx)
    program.smooth_rate = 0.5

    program.render([depth_image(ctx, 0.0)])
    first = program.norender()
    program.render([depth_image(ctx, 1.0)])
    second = program.norender()

    assert first is not second
    # If history were lost, the second frame would adopt 1.0 outright.
    assert read(program)[0] == pytest.approx(0.5, abs=1e-5)


def test_defaults_are_sane(ctx):
    program = make_program(ctx)

    assert program.smooth_rate == DEFAULT_SMOOTH_RATE
    assert program.hold_frames == DEFAULT_HOLD_FRAMES
    assert 0.0 < DEFAULT_SMOOTH_RATE < 1.0
