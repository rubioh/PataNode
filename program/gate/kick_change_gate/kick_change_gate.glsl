#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float energy_low;
uniform float sens;
uniform float mode;
uniform vec2 translate;
uniform float camp;
uniform float which;

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;
    vec4 col = texture(iChannel0, uv);
    fragColor = col*which;

}
