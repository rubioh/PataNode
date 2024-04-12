#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D iChannel0;

#define R iResolution
void main()
{
    vec2 uv = gl_FragCoord.xy/R;
    vec3 col = texture(iChannel0, uv).rgb;
    fragColor = vec4(col,1.0);

}
