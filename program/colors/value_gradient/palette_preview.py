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
    palette = [
        0.5 + 0.5 * math.cos(TWO_PI * (frequency * t + phase)) for phase in phases
    ]
    hue, sat, _ = colorsys.rgb_to_hsv(*palette)
    return colorsys.hsv_to_rgb(hue, sat * saturation, t)
