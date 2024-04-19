#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;

uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform float baseBlend;
uniform float bias;
uniform vec2 offset1;
uniform vec2 offset2;

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    vec3 col1 = texture(iChannel0, uv + offset1).rgb;
    vec3 col2 = texture(iChannel1, uv + offset2).rgb;

    float mixFactor = min(1., baseBlend + bias);
    vec3 col = mix(col1, col2, mixFactor);
    fragColor = vec4(col,1.0);
}
