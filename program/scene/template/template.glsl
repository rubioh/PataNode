#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
#define PI 3.141593

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;
    float t = iTime * .001;
    vec3 col = cos(vec3(uv.x+t*.94, uv.y+t*1.04, uv.x-t*1.11));

    col = fract(pow(col*2., vec3(1.7, 1.1, 1.2)));
    col.b *= (7.85);
    col.rg *= vec2(3.75, 8.15);
    col = pow(col*.9, vec3(1.3, .7,.9));
    col = tanh(col);
    // Output to screen
    col = pow(col, vec3(2.2));
    float tmp = col.g;
    col.g = 0.;
    col.r += tmp;
    col.r *=.5;

    tmp = mix(.0, 1., col.r*col.g);
    col.g = tmp;

    fragColor = vec4(col, 1.);
}

