#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform usampler2D depth_map;
uniform float near_mm;
uniform float far_mm;
uniform float depth_scale;
uniform float flip_x;
uniform float flip_y;
uniform float oscillate;
uniform float period_mm;

// Keep comments out of the declaration block above, and keep the word that
// starts each of those declarations out of the prose down here.
// ProgramsUniforms.addProgram parses this file by splitting on ";" and reading
// the third space-separated token of any chunk containing that word, so either
// slip registers a phantom entry that ends up written into saved scene files.
//
// depth_map is R16UI: an integer sampler, NEAREST filtering only. This is
// deliberate -- linear filtering across a depth discontinuity interpolates
// foreground into background and invents surfaces that were never measured.
// Do not "fix" this to a sampler2D.
//
// depth_scale converts raw sensor units to millimetres.
// flip is 0 or 1 per axis.
// oscillate is 0 or 1: off is the near..far ramp, on is the banded mode.
// period_mm is the distance covered by one full band cycle.

const float TAU = 6.283185307179586;

void main()
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;
    uv = mix(uv, 1.0 - uv, vec2(flip_x, flip_y));

    uint raw = texture(depth_map, uv).r;

    // 0 means the sensor measured nothing here: a shadow, a dark or shiny
    // surface, out of range -- or no camera connected at all. Both cases are
    // reported the same way, as alpha 0.
    if (raw == 0u) {
        fragColor = vec4(0.0);
        return;
    }

    float mm = float(raw) * depth_scale;
    // Guard the divide here rather than in Python: the inspector drives these
    // through expressions, so near and far can coincide at bind time without
    // the bound values ever being equal. Defensive -- on this NVIDIA driver
    // clamp() already turns the resulting NaN into 0.0, but GLSL leaves
    // clamp(NaN) undefined, so other drivers may propagate it.
    float range = far_mm - near_mm;
    if (abs(range) < 1e-6) {
        range = 1.0;
    }

    float d = clamp((mm - near_mm) / range, 0.0, 1.0);

    if (oscillate > 0.5) {
        // Contour bands instead of one ramp across the whole window: a hand
        // moving 100mm crosses a whole cycle rather than shifting the output
        // by 0.03, so downstream motion reads displacement at the scale of the
        // subject rather than at the scale of the room.
        //
        // Driven off d * range rather than raw mm so the near/far window still
        // means something here: it is exactly (mm - near_mm) clamped to the
        // window, which freezes everything outside it on a flat value instead
        // of letting out-of-range sensor junk band away past far_mm. Negative
        // when near/far are swapped, which cos absorbs, so the inverted case
        // keeps working.
        float offset_mm = d * range;

        // Guarded like range above: the inspector drives this through
        // expressions, so a period of 0 is reachable at bind time and would
        // divide by zero on every measured pixel.
        float period = max(abs(period_mm), 1e-3);

        // cos, not fract: a sawtooth snaps 1 -> 0 at every band edge, and the
        // motion nodes downstream read that seam as a full-scale jump that no
        // object actually made. Phase is anchored at near_mm, so band edges sit
        // at fixed distances from the camera rather than drifting with far_mm.
        d = 0.5 - 0.5 * cos(TAU * offset_mm / period);
    }

    fragColor = vec4(vec3(d), 1.0);
}
