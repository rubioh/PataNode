#version 330
layout (location=0) out vec4 fragColor;

void main()
{
    vec2 uv = gl_FragCoord.xy;
    fragColor = vec4(1.);

}
