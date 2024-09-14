#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;


#define R iResolution

void main()
{
    vec2 uv = gl_FragCoord.xy/R;
    vec4 id = texture(iChannel0, uv).rgba;
    fragColor = vec4(id);
}
