#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;

// R16UI: an integer sampler, NEAREST filtering only. This is deliberate --
// linear filtering across a depth discontinuity interpolates foreground into
// background and invents surfaces that were never measured. Do not "fix" this
// to a sampler2D.
uniform usampler2D depth_map;

uniform float near_mm;
uniform float far_mm;
uniform float depth_scale;   // raw sensor units -> millimetres
uniform vec2 flip;           // 0 or 1 per axis

void main()
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;
    uv = mix(uv, 1.0 - uv, flip);

    uint raw = texture(depth_map, uv).r;

    // 0 means the sensor measured nothing here: a shadow, a dark or shiny
    // surface, out of range -- or no camera connected at all. Both cases are
    // reported the same way, as alpha 0.
    if (raw == 0u) {
        fragColor = vec4(0.0);
        return;
    }

    float mm = float(raw) * depth_scale;
    float d = clamp((mm - near_mm) / (far_mm - near_mm), 0.0, 1.0);

    fragColor = vec4(vec3(d), 1.0);
}
