#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform usampler2D depth_map;
uniform float near_mm;
uniform float far_mm;
uniform float depth_scale;
uniform float flip_x;
uniform float flip_y;

// depth_map is R16UI: an integer sampler, NEAREST filtering only. This is
// deliberate -- linear filtering across a depth discontinuity interpolates
// foreground into background and invents surfaces that were never measured.
// Do not "fix" this to a sampler2D.
//
// depth_scale converts raw sensor units to millimetres.
// flip is 0 or 1 per axis.

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

    fragColor = vec4(vec3(d), 1.0);
}
