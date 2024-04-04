#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform sampler2D SST;
uniform float sigma;
uniform float k;

#define R iResolution
#define PI 3.1415

float ColorFetch(vec2 coord, int i){
    vec2 tex = texture(iChannel0, coord/R.xy).rg;
    if (i == 0){
        return tex.r;
    }
    else{
        return tex.g;
    }
}

float gaussian(float s, float pos){
    return exp(-(pos*pos)/(2.*s*s));
}

#define D(W) texture(SST, W/R.xy)

void main()
{

    vec2 uv = gl_FragCoord.xy;

    float G1 = 0.0, G2 = .0;
    float sum1 = .0;
    float sum2 = .0;

    float w1 = gaussian(sigma, 0.);
    G1 += ColorFetch(uv, 0)*w1;
    sum1 += w1;
    float w2 = gaussian(sigma*k, 0.);
    G2 += ColorFetch(uv, 1)*w2;
    sum2 += w2;


    vec2 dir = D(uv).xy;
    vec2 where = uv + dir;

    for (float i = 1. ; i<(2.*sigma*k + 1.) ; i++){
        w1 = gaussian(sigma, i);
        w2 = gaussian(sigma*k, i);

        G1 += ColorFetch(where, 0)*w1;
        G2 += ColorFetch(where, 1)*w2;

        sum1 += w1;
        sum2 += w2;

        vec2 ndir = D(where).xy;
        if (abs(ndir.x)>abs(ndir.y)){
            ndir *= sign(ndir.x)*sign(dir.x);
        }
        else{
            ndir *= sign(ndir.y)*sign(dir.y);
        }
        dir = ndir;
        where += dir;

    }
    dir = -D(uv).xy;
    where = uv + dir;
    for (float i = 1. ; i<(2.*sigma*k + 1.) ; i++){
        w1 = gaussian(sigma, i);
        w2 = gaussian(sigma*k, i);

        G1 += ColorFetch(where, 0)*w1;
        G2 += ColorFetch(where, 1)*w2;
        sum1 += w1;
        sum2 += w2;

        vec2 ndir = D(where).xy;
        if (abs(ndir.x)>abs(ndir.y)){
            ndir *= sign(ndir.x)*sign(dir.x);
        }
        else{
            ndir *= sign(ndir.y)*sign(dir.y);
        }
        dir = ndir;
        where += dir;
    }

    G1 /= sum1;
    G2 /= sum2;

    fragColor = vec4(G1, G2, .0, .0);
}
