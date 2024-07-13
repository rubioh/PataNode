#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform float x_offset;
uniform float y_offset;
uniform float x_offset_fine;
uniform float y_offset_fine;
uniform float zoom;
uniform sampler2D iChannel0;

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 R = iResolution.xy;
    vec2 uv = (gl_FragCoord.xy*2.-R.xy)/R.y;
    uv += vec2(x_offset + x_offset_fine, y_offset + y_offset_fine);
    uv *= R.y;
    uv += R.xy;
    uv /= 2.;
    uv /= R.xy;
    uv = (uv-.5)*zoom + .5;

    vec3 col = texture(iChannel0, uv).rgb;
    col *= smoothstep(1.05, .9, 2.*length(uv -.5) );

    fragColor = vec4(col,1.0);
}
