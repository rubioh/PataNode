#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;

uniform sampler2D iChannel0;
uniform float sigmaC;

#define R iResolution

vec4 ColorFetch(ivec2 coord){
    return texelFetch(iChannel0, coord, 0);
}

float gaussian(float s, float pos){
    return exp(-(pos*pos)/(2.*s*s));
}

void main()
{
    ivec2 uv = ivec2(gl_FragCoord.xy);
    vec4 g = vec4(0.0);

    float sum = .0;

    float w = gaussian(sigmaC, 0.);
    g += ColorFetch(uv)*w;
    sum += w;

    for (float i = 1. ; i<(2.*sigmaC+1.) ; i++){
        w = gaussian(sigmaC, float(i));
        g += ColorFetch(uv + ivec2(i,0))*w;
        g += ColorFetch(uv - ivec2(i,0))*w;
        sum += 2.*w;
    }
    g /= sum ;
    fragColor = g;
}
