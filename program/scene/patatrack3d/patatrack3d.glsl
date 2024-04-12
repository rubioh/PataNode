#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float energy;
#define R iResolution
void main()
{
    vec2 uv = gl_FragCoord.xy/R.xy;
    vec4 res = texture(iChannel0, uv- vec2(.5)/R.xy).rgba;
    res.rgb = clamp(res.rgb, vec3(0.), vec3(1.));
    fragColor = vec4(res.rgb, pow(length(res), .5)*5.*energy*res.a);
}
