#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;

#define R iResolution

void main()
{
    vec2 uv = gl_FragCoord.xy/R.xy;

    // Anti Aliasing
    vec4 res = texture(iChannel0, uv);
    fragColor = vec4(res);
}
