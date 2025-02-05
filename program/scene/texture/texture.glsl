#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;

uniform sampler2D iChannel0;
void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;

    fragColor = vec4(texture(iChannel0, uv).rgba);
}

