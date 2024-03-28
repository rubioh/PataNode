#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D UVState;
uniform sampler2D iChannel0;


void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;
    vec2 R = iResolution.xy;
    vec2 uv_curl = texture(UVState, uv).rg;
    fragColor = texture(iChannel0, uv_curl);
}
