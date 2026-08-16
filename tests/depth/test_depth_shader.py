"""Headless check of the depth normalisation shader.

This is the one GL behaviour worth automating: whether moderngl's dtype="u2"
produces a texture that a usampler2D can read. Everything else about the node
needs the running app.
"""

import os

import numpy as np
import pytest

moderngl = pytest.importorskip("moderngl")

# Anchored on this file's location, not the process cwd: pytest may be
# invoked from anywhere, and a cwd-relative path would raise FileNotFoundError
# whenever the suite isn't run from the repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHADER_PATH = os.path.join(
    REPO_ROOT, "program", "input", "depth_input", "depth_input.glsl"
)
VERTEX_PATH = os.path.join(REPO_ROOT, "program", "base", "vertex_base.glsl")


@pytest.fixture
def ctx():
    try:
        context = moderngl.create_standalone_context()
    except Exception as error:
        pytest.skip("no standalone GL context available: %s" % error)
    yield context
    context.release()


def render_depth_frame(
    ctx,
    depths_mm,
    near_mm=500.0,
    far_mm=4000.0,
    flip=(0.0, 0.0),
    depth_scale=1.0,
    oscillate=0.0,
    period_mm=500.0,
):
    """Render a 1-row depth image through the shader.

    depths_mm is a sequence of raw texel values, one per output column.
    Returns an (len(depths_mm), 4) array: one RGBA pixel per column.
    """
    width = len(depths_mm)

    with open(VERTEX_PATH) as handle:
        vertex_source = handle.read()
    with open(SHADER_PATH) as handle:
        fragment_source = handle.read()

    program = ctx.program(vertex_shader=vertex_source, fragment_shader=fragment_source)

    texture = ctx.texture((width, 1), components=1, dtype="u2")
    texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
    texture.write(np.array([depths_mm], dtype=np.uint16))
    texture.use(0)

    program["depth_map"] = 0
    program["near_mm"] = near_mm
    program["far_mm"] = far_mm
    program["depth_scale"] = depth_scale
    program["flip_x"], program["flip_y"] = flip
    program["oscillate"] = oscillate
    program["period_mm"] = period_mm
    program["iResolution"] = (float(width), 1.0)

    quad = ctx.buffer(np.array([-1, -1, 3, -1, -1, 3], dtype="f4").tobytes())
    vao = ctx.vertex_array(program, [(quad, "2f", "in_position")])

    fbo = ctx.framebuffer([ctx.texture((width, 1), 4, dtype="f4")])
    fbo.use()
    fbo.clear(0.0, 0.0, 0.0, 0.0)
    vao.render(moderngl.TRIANGLES)

    pixels = np.frombuffer(fbo.read(components=4, dtype="f4"), dtype="f4")
    return pixels.reshape((width, 4))


def render_depth(ctx, depth_mm, near_mm=500.0, far_mm=4000.0, flip=(0.0, 0.0)):
    """Render a single-texel depth image through the shader and return its RGBA pixel."""
    return render_depth_frame(
        ctx, [depth_mm], near_mm=near_mm, far_mm=far_mm, flip=flip
    )[0]


def render_banded(ctx, depth_mm, period_mm=500.0, near_mm=500.0, far_mm=4000.0):
    """Render one texel with the banded mode on, and return its red channel."""
    return render_depth_frame(
        ctx,
        [depth_mm],
        near_mm=near_mm,
        far_mm=far_mm,
        oscillate=1.0,
        period_mm=period_mm,
    )[0][0]


def test_a_measured_pixel_is_opaque(ctx):
    pixel = render_depth(ctx, depth_mm=2250)

    assert pixel[3] == pytest.approx(1.0)


def test_depth_is_normalised_between_near_and_far(ctx):
    pixel = render_depth(ctx, depth_mm=2250, near_mm=500.0, far_mm=4000.0)

    # 2250mm is the midpoint of 500..4000
    assert pixel[0] == pytest.approx(0.5, abs=1e-3)


def test_an_unmeasured_pixel_is_transparent(ctx):
    pixel = render_depth(ctx, depth_mm=0)

    assert pixel[3] == pytest.approx(0.0)


def test_depth_is_clamped_outside_the_near_far_window(ctx):
    assert render_depth(ctx, depth_mm=100)[0] == pytest.approx(0.0)
    assert render_depth(ctx, depth_mm=9000)[0] == pytest.approx(1.0)


def test_swapping_near_and_far_inverts_the_ramp(ctx):
    normal = render_depth(ctx, depth_mm=1000, near_mm=500.0, far_mm=4000.0)
    inverted = render_depth(ctx, depth_mm=1000, near_mm=4000.0, far_mm=500.0)

    assert inverted[0] == pytest.approx(1.0 - normal[0], abs=1e-3)


def test_flip_x_swaps_which_texel_is_sampled(ctx):
    # A 1x1 texture can't observe flip at all -- every uv lands on the same
    # texel regardless. Use two distinct texels so a swap is visible.
    depths = [1000, 3000]
    normal = render_depth_frame(ctx, depths, flip=(0.0, 0.0))
    flipped = render_depth_frame(ctx, depths, flip=(1.0, 0.0))

    assert flipped[0][0] == pytest.approx(normal[1][0], abs=1e-3)
    assert flipped[1][0] == pytest.approx(normal[0][0], abs=1e-3)


def test_the_ramp_is_untouched_while_oscillate_is_off(ctx):
    # The whole banded branch has to be inert at 0, or every scene saved before
    # it existed renders differently after this change.
    plain = render_depth_frame(ctx, [2250], oscillate=0.0, period_mm=500.0)[0]

    assert plain[0] == pytest.approx(0.5, abs=1e-3)


def test_the_band_repeats_every_period(ctx):
    # 500mm apart at a 500mm period: same point in the cycle, same value. Picked
    # off a cycle boundary so this can't pass on both landing at 0.
    first = render_banded(ctx, 1100, period_mm=500.0)
    second = render_banded(ctx, 1600, period_mm=500.0)
    third = render_banded(ctx, 2100, period_mm=500.0)

    assert first == pytest.approx(second, abs=2e-3)
    assert second == pytest.approx(third, abs=2e-3)
    # Guard against a degenerate shader that returns a constant everywhere.
    assert first != pytest.approx(render_banded(ctx, 1225, period_mm=500.0), abs=0.05)


def test_the_cycle_is_anchored_at_near_and_peaks_at_half_a_period(ctx):
    # Bands sit at fixed distances from the camera: a trough exactly on
    # near_mm, a crest half a period further out.
    assert render_banded(ctx, 500, period_mm=500.0) == pytest.approx(0.0, abs=1e-3)
    assert render_banded(ctx, 750, period_mm=500.0) == pytest.approx(1.0, abs=1e-3)
    assert render_banded(ctx, 1000, period_mm=500.0) == pytest.approx(0.0, abs=1e-3)


def test_a_shorter_period_packs_more_bands_into_the_window(ctx):
    # The parameter has to read as a distance, not an arbitrary knob: halving
    # it must put the same phase at half the offset from near_mm.
    coarse = render_banded(ctx, 1000, period_mm=500.0)
    fine = render_banded(ctx, 750, period_mm=250.0)

    assert coarse == pytest.approx(fine, abs=2e-3)


def test_banding_reacts_to_small_moves_far_harder_than_the_ramp(ctx):
    # This is the reason the mode exists. A 100mm move at 2000mm shifts the
    # plain ramp by ~0.03 -- invisible to anything downstream -- while the
    # banded output swings an order of magnitude more.
    ramp_delta = abs(render_depth(ctx, 2100)[0] - render_depth(ctx, 2000)[0])
    banded_delta = abs(
        render_banded(ctx, 2100, period_mm=500.0)
        - render_banded(ctx, 2000, period_mm=500.0)
    )

    assert ramp_delta < 0.05
    assert banded_delta > 10 * ramp_delta


def test_an_unmeasured_pixel_stays_transparent_when_banded(ctx):
    # Raw 0 must short-circuit before the banding, or "no measurement" would
    # come back as a legitimate-looking band value at alpha 1.
    pixel = render_depth_frame(ctx, [0], oscillate=1.0, period_mm=500.0)[0]

    assert pixel[3] == pytest.approx(0.0)


def test_depths_beyond_the_window_freeze_on_one_value(ctx):
    # Banding is driven through the clamped window, so out-of-range sensor
    # junk sits on a flat value instead of continuing to band away past far_mm.
    assert render_banded(ctx, 5000, period_mm=500.0) == pytest.approx(
        render_banded(ctx, 9000, period_mm=500.0), abs=1e-3
    )
    assert render_banded(ctx, 100, period_mm=500.0) == pytest.approx(
        render_banded(ctx, 300, period_mm=500.0), abs=1e-3
    )


def test_a_zero_period_does_not_blow_up(ctx):
    # The inspector drives period_mm through expressions, so 0 is reachable at
    # bind time. Dividing by it would put NaN on every measured pixel.
    pixel = render_depth_frame(ctx, [2250], oscillate=1.0, period_mm=0.0)[0]

    assert np.isfinite(pixel[0])
    assert 0.0 <= pixel[0] <= 1.0
    assert pixel[3] == pytest.approx(1.0)


def test_banding_survives_a_swapped_near_and_far(ctx):
    # d * range goes negative when the window is inverted; cos absorbs the
    # sign, so the mode has to keep working rather than flatten to a constant.
    inverted = [
        render_banded(ctx, mm, period_mm=500.0, near_mm=4000.0, far_mm=500.0)
        for mm in (1000, 1125, 1250)
    ]

    assert all(np.isfinite(value) for value in inverted)
    assert max(inverted) - min(inverted) > 0.1


def test_depth_scale_multiplies_the_raw_value(ctx):
    # 22500 raw units * 0.1 depth_scale = 2250mm, the midpoint of 500..4000.
    # Without the multiplication, 22500mm would clamp to the far edge (1.0)
    # instead of landing on the midpoint (0.5).
    pixel = render_depth_frame(
        ctx, [22500], near_mm=500.0, far_mm=4000.0, depth_scale=0.1
    )[0]

    assert pixel[0] == pytest.approx(0.5, abs=1e-3)
