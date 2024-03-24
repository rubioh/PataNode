#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
#define PI 3.141593

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;

    vec3 col = cos(vec3(uv.x+iTime, uv.y+iTime, uv.x-iTime));

    col = fract(col*4.);
    // Output to screen
    fragColor = vec4(col,1.0);
}

