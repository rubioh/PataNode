#version 330 core
layout (location=0) out vec4 fragColor;

uniform sampler2D iChannel0;
uniform vec2 iResolution;
uniform float white;
#define PI 3.141593
in vec2 tcs;

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution.xy;
    vec2 my_tcs = vec2(tcs.x, 1.-tcs.y);
    if (white > .0)
        fragColor = vec4(1.);
    else
        fragColor = texture(iChannel0, my_tcs);
}