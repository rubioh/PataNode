"""Tests for the DepthInput program itself, on a real GL context.

The shader tests next door compile the .glsl file directly and set uniforms by
hand, so they never exercise DepthInput. That leaves the seams where this
branch's real bugs actually lived: the uniform-name/binding-key correspondence
(a typo there is a runtime KeyError and nothing else), the GLSL comment
placement that the uniform parser is sensitive to, and texture reallocation
when a reconnect returns a different profile.

Skips rather than fails without a usable GL context, so the suite still runs on
a headless machine with no GPU.
"""

from types import SimpleNamespace

import moderngl
import numpy as np
import pytest

from depth.depth_engine import DepthEngine
from depth.depth_source import SyntheticSource
from program.input.depth_input.depth_input import (
    DEFAULT_FAR_MM,
    DEFAULT_NEAR_MM,
    DEFAULT_OSCILLATE,
    DEFAULT_PERIOD_MM,
    DepthInput,
    DepthInputNode,
)

WIN_SIZE = (320, 180)

# Every uniform declared in depth_input.glsl. ProgramsUniforms.addProgram parses
# the shader by splitting on ";" and taking chunk.split(" ")[2] as the name, so
# a comment placed between uniform declarations registers a phantom uniform that
# ends up written into saved scene files. Pinning the set here makes that
# regression fail a test instead of quietly corrupting saves.
EXPECTED_UNIFORMS = {
    "iResolution",
    "depth_map",
    "near_mm",
    "far_mm",
    "depth_scale",
    "flip_x",
    "flip_y",
    "oscillate",
    "period_mm",
}

# depth_map is a sampler unit and depth_scale is reported by the sensor;
# neither is meaningful to drive from an inspector expression.
PROTECTED_UNIFORMS = {"depth_map", "depth_scale"}


@pytest.fixture(scope="module")
def ctx():
    try:
        context = moderngl.create_standalone_context()
    except Exception as error:
        pytest.skip(f"no usable GL context: {error}")
    yield context
    context.release()


def make_program(ctx, engine=None):
    program = DepthInput(ctx=ctx, win_size=WIN_SIZE, engine=engine)
    # ProgramBase leaves fbos unset; the node normally supplies them.
    program.connectFbos(
        [ctx.framebuffer(color_attachments=[ctx.texture(WIN_SIZE, 4, dtype="f4")])]
    )
    return program


def make_engine(width=64, height=32):
    return DepthEngine(
        lambda: SyntheticSource(
            width=width, height=height, fps=1000, sleep_fn=lambda _s: None
        )
    )


def wait_for_frame(engine, timeout=2.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        if engine.get_frame() is not None:
            return True
        time.sleep(0.01)
    return False


def test_the_shader_registers_exactly_the_declared_uniforms(ctx):
    program = make_program(ctx)

    parsed = set(program.programs_uniforms.uniforms[""].keys())

    # Equality, not a subset: an extra entry here is a phantom uniform, and
    # phantom uniforms get serialised into .pn scene files.
    assert parsed == EXPECTED_UNIFORMS


def test_protected_uniforms_get_no_inspector_entry(ctx):
    program = make_program(ctx)

    # ProgramBase keys these by program_name + "program"; this program's name
    # is the empty string.
    exposed = set(program.adaptable_parameters_dict["program"].keys())

    # The four the user is meant to drive, and nothing else.
    assert exposed == EXPECTED_UNIFORMS - PROTECTED_UNIFORMS - {"iResolution"}
    assert not exposed & PROTECTED_UNIFORMS


def test_every_binding_target_exists_as_an_attribute(ctx):
    # bindUniform reads these off the program by name, so a binding key that
    # names a uniform the shader does not declare, or a target attribute that
    # initParams never sets, is a KeyError/AttributeError at render time only.
    program = make_program(ctx)

    for uniform_name in program.programs_uniforms.uniforms[""]:
        if uniform_name == "depth_map":
            continue  # bound explicitly in render(), not through the binding
        assert hasattr(program, uniform_name) or uniform_name == "iResolution"

    assert program.near_mm == DEFAULT_NEAR_MM
    assert program.far_mm == DEFAULT_FAR_MM


def test_the_banded_mode_is_off_by_default(ctx):
    # Scenes saved before this mode existed carry no value for either uniform,
    # so deserialize leaves the defaults in place. They have to reproduce the
    # plain near..far ramp those scenes were built against.
    program = make_program(ctx)

    assert program.oscillate == DEFAULT_OSCILLATE == 0.0
    assert program.period_mm == DEFAULT_PERIOD_MM


def test_without_an_engine_it_renders_transparent_black(ctx):
    program = make_program(ctx, engine=None)

    program.render()
    pixels = np.frombuffer(program.fbos[0].read(components=4, dtype="f4"), dtype="f4")

    # The 1x1 zero texture means "unmeasured everywhere", which is alpha 0 --
    # the same signal as a hole, deliberately.
    assert not pixels.any()


def test_a_frame_reaches_the_texture_and_changes_the_output(ctx):
    engine = make_engine()
    engine.acquire()
    try:
        assert wait_for_frame(engine)

        program = make_program(ctx, engine=engine)
        program.render()
        pixels = np.frombuffer(
            program.fbos[0].read(components=4, dtype="f4"), dtype="f4"
        )
    finally:
        engine.release()
        engine.close()

    # SyntheticSource spans 500..4000mm, exactly the default near/far, so the
    # output must contain real measurements rather than the empty texture.
    assert pixels.any()


def test_the_texture_follows_a_profile_change_on_reconnect(ctx):
    engine = make_engine(width=64, height=32)
    engine.acquire()
    try:
        assert wait_for_frame(engine)
        program = make_program(ctx, engine=engine)
        program.updateParams()

        assert program.depth_texture.size == (64, 32)
    finally:
        engine.release()
        engine.close()

    # A reconnect can come back on a different profile; the node must
    # reallocate rather than upload a mismatched buffer.
    bigger = make_engine(width=128, height=64)
    bigger.acquire()
    try:
        assert wait_for_frame(bigger)
        program.engine = bigger
        program._last_frame_id = 0
        program.updateParams()

        assert program.depth_texture.size == (128, 64)
    finally:
        bigger.release()
        bigger.close()


def test_reload_program_reinjects_the_engine(ctx):
    """The node must not come back engine-less from the Resolution menu.

    ShaderNode.reload_program rebuilds the program via
    self.program.__class__(ctx=..., win_size=...), dropping the engine kwarg
    entirely, which made the node render a permanently transparent 1x1 texture
    with no error from any saved scene. DepthInputNode overrides it.

    Driving the real method needs a node, and constructing one needs a Qt
    scene, so the instance is built without __init__ and given only what
    reload_program touches. That is enough for this to fail if the override is
    removed -- which asserting on a constructor kwarg was not.
    """
    engine = make_engine()
    node = DepthInputNode.__new__(DepthInputNode)
    node.engine = engine
    node.scene = SimpleNamespace(ctx=ctx)
    node.win_size = WIN_SIZE
    node.program = make_program(ctx, engine=engine)

    # Everything reload_program calls that belongs to the graph, not to us.
    node.serialize = lambda: {}
    node.deserialize = lambda state, restore_window_size=False: None
    node.markDirty = lambda: None
    node.eval = lambda: None

    node.reload_program()

    assert node.program.engine is engine
