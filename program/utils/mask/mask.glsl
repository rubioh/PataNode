#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;

uniform sampler2D iChannel0;
uniform sampler2D iChannel1;

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    vec3 col1 = texture(iChannel0, uv).rgb;
    vec3 col2 = texture(iChannel1, uv).rgb;
    vec3 col = col1 * col2;
    fragColor = vec4(col, 1.0);
}
