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
