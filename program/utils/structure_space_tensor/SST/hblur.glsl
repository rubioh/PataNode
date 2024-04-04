#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform sampler2D iChannel0;
uniform float sigmaC;

#define R iResolution
#define PI 3.1415

vec4 ColorFetch(ivec2 coord){
    return texelFetch(iChannel0, coord, 0);
}

float gaussian(float s, float pos){
    return exp(-(pos*pos)/(2.*s*s));
}


void main()
{
    ivec2 uv = ivec2(gl_FragCoord.xy);

    vec4 g = vec4(0.);
    float sum = .0;

    // i = 0
    float w = gaussian(sigmaC, 0.);
    g += ColorFetch(uv)*w;
    sum += w;

    for (float i = 1. ; i<(2.*sigmaC+1.) ; i++){
        w = gaussian(sigmaC, float(i));
        g += ColorFetch(uv + ivec2(0,i))*w;
        g += ColorFetch(uv - ivec2(0,i))*w;
        sum += 2.*w;
    }

    g /= sum;
    fragColor = vec4(g);
    /*
    float lambda1 = .5*(g.x + g.y + sqrt(g.y*g.y - 2.*g.y*g.x + g.x*g.x + 4.*g.z*g.z));
    vec2 d = vec2(-g.x + lambda1, -g.z);
    if (d.x>0) d *= -1.;

    vec4 res = (length(d) != 0.) ? vec4(normalize(d), sqrt(lambda1), 1.) : vec4(.0,1.,0.,1.);
    fragColor = res;
    */
}
