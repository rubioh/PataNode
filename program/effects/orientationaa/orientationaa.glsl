#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D BaseTex;
uniform sampler2D SST;
uniform float sigmaA;

#define D(W) texture(SST, W/R.xy)

#define R iResolution
#define PI 3.1415

vec3 ColorFetch(vec2 coord, int i){
    return texture(BaseTex, coord/R.xy).rgb;
}
float gaussian(float s, float p){
    return exp(-(p*p)/(2.*s*s));
}

void main()
{
    vec2 uv = gl_FragCoord.xy;
    if (uv.x <= .5){
        fragColor = texture(BaseTex, uv/R.xy);
        return;
    }

    vec3 G1 = vec3(0.0);
    float sum1 = .0;

    float w1 = gaussian(sigmaA, 0.);
    G1 += ColorFetch(uv, 0)*w1;
    sum1 += w1;

    vec2 dir = D(uv).xy;
    vec2 where = uv + dir;

    for (float i = 1. ; i<(2.*sigmaA + 1.) ; i++){
        w1 = gaussian(sigmaA, i);
        G1 += ColorFetch(where, 0)*w1;
        sum1 += w1;

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
    for (float i = 1. ; i<(2.*sigmaA + 1.) ; i++){
        w1 = gaussian(sigmaA, i);

        G1 += ColorFetch(where, 0)*w1;
        sum1 += w1;

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
    fragColor = vec4(G1, 1.0);
}
