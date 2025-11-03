#version 330 core
layout (location=0) out vec4 fragColor;

uniform sampler2D tex;
uniform vec2 iResolution;
uniform vec2 flip_y;
#define PI 3.141593

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution.xy;
    fragColor = vec4(texture(tex, vec2(uv.x, flip_y.x - uv.y * flip_y) ).rgb, 1.0);
}

