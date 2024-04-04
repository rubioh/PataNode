#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform sampler2D SST;
uniform float sigmaE;
uniform float k;

#define R iResolution
#define PI 3.1415

float ColorFetch(vec2 coord){
    //return dot(texture(iChannel0, vec2(coord)/R.xy).rgb, vec3(.299, .587, .114));
    return dot(texture(iChannel0, vec2(coord)/R.xy).rgb, vec3(.212, .7152, .0722));
}

float gaussian(float s, float pos){
    return exp(-(pos*pos)/(2.*s*s));
}

#define D(W) texture(SST, W/R.xy)

void main()
{
    vec2 uv = gl_FragCoord.xy;
    float G1 = 0., G2 = .0;

    float sum1 = .0;
    float sum2 = .0;

    float w1 = gaussian(sigmaE, 0.);
    G1 += ColorFetch(uv)*w1;
    sum1 += w1;
    float w2 = gaussian(sigmaE*k, 0.);
    G2 += ColorFetch(uv)*w2;
    sum2 += w2;

    vec2 dir = D(uv).xy;
    vec2 n = vec2(dir.y, -dir.x);
    vec2 nabs = abs(n);
    float ds = 1.0 / ((nabs.x > nabs.y) ? nabs.x : nabs.y);
    for (float i = 1 ; i<2.*sigmaE*k+1. ; i+=1.){
        w1 = gaussian(sigmaE, i*ds);
        w2 = gaussian(sigmaE*k, i*ds);

        float c1 = ColorFetch(uv + n*i*ds);
        float c2 = ColorFetch(uv - n*i*ds);

        G1 += c1*w1;
        G1 += c2*w1;

        G2 += c1*w2;
        G2 += c2*w2;

        sum1 += 2.*w1;
        sum2 += 2.*w2;
    }

    G1 /= sum1;
    G2 /= sum2;

    fragColor = vec4(G1, G2, .0,.0);

}
