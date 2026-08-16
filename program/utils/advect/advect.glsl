#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform float advect_amount;

// iChannel0: content being advected.
// iChannel1: flow field -- RG = uv/frame velocity (Motion Flow's packed
// output). Deliberately not commented inline above: program_base.py parses
// uniform names by splitting the source on ";" then on spaces, so a trailing
// "//" comment on a uniform line shifts the token index and drops the name.

void main()
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;

    // Motion Flow's RG is already signed flow in uv-units-per-frame -- no
    // resolution rescale here (unlike program/utils/fluid/ADF/advect.glsl,
    // which is a pixels-per-frame contract for a different, internal use).
    vec2 flow = texture(iChannel1, uv).rg;

    // Semi-Lagrangian backward sample: pull from where this pixel's content
    // came from one (scaled) frame ago.
    vec2 src_uv = uv - flow * advect_amount;

    fragColor = texture(iChannel0, src_uv);
}
