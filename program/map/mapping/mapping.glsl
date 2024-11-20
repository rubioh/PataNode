#version 330 core
layout (location=0) out vec4 fragColor;

uniform sampler2D iChannel0;
uniform vec2 iResolution;
#define PI 3.141593
in vec2 tcs;

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution.xy;
    fragColor = texture(iChannel0, tcs+iResolution.x);
}