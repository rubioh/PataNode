#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D AccumTex;
uniform float magnitude_scale;

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution;

    // Bilinear upscale back to output resolution.
    vec4 acc = texture(AccumTex, uv);

    vec2 flow = acc.xy;
    float mag = clamp(length(flow)*magnitude_scale, 0., 1.);

    // RG: signed flow in UV units per frame, consumable as-is by fluid's velocity
    // input. B: motion magnitude, for use as a mask. A: estimate confidence.
    fragColor = vec4(flow, mag, acc.a);
}
