#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;

uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform float x1;
uniform float x2;
void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    vec3 col1 = texture(iChannel0, uv).rgb;
    vec3 col2 = texture(iChannel1, uv).rgb;

    float lum = col1.x+col1.y+col1.z;

    float grad = smoothstep(x1, x2, lum);
    vec3 col = mix(col1+col2, col1, grad);
    fragColor = vec4(col,1.0);
}
