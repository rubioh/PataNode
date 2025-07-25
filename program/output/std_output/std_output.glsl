#version 330 core
layout (location=0) out vec4 fragColor;

uniform sampler2D tex;
uniform vec2 iResolution;
#define PI 3.141593

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution.xy;
    fragColor = texture(tex, uv);
}

