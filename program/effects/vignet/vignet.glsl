#version 330 core
layout (location=0) out vec4 fragColor;

uniform float decay;
uniform float intensity;
uniform vec2 iResolution;
uniform sampler2D iChannel0;

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution;
    float l = length((-iResolution.xy + 2.0*gl_FragCoord.xy)/iResolution.y);

    vec3 col = texture(iChannel0, uv).rgb;
    float i = intensity;

    col *= 1. - smoothstep(i, i + decay, l);
    fragColor = vec4(vec3(col),1.0);
}
