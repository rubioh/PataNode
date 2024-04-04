#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D BaseTex;
uniform sampler2D DoG;
uniform sampler2D Hatch;
uniform float tau;
uniform float eps;
uniform float phi;
uniform float mode;

float sdSegment( in vec2 p, in vec2 a, in vec2 b )
{
    vec2 pa = p-a, ba = b-a;
    float h = clamp( dot(pa,ba)/dot(ba,ba), 0.0, 1.0 );
    return length( pa - ba*h );
}
#define R iResolution
void main()
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;

    vec2 G = texture(DoG, uv).xy;
    float G1 = G.x*10.;
    float G2 = G.y*10.;

    float DoG = (1.+tau)*G1 - tau*G2;
    if (mode!=3)
        DoG = step(eps, DoG) + (1.-step(eps,DoG))*(1.+tanh(  phi * (DoG - eps)));

    vec3 col = vec3(DoG);
    if (mode == 0){
        col = DoG*texture(BaseTex, uv).rgb;
    }
    if (mode == 1){
        vec3 tex = texture(BaseTex, uv).rgb;
        col = mix(vec3(0.), tex, DoG);
    }
    if (mode == 2){
        vec3 tex = texture(BaseTex, uv).rgb;
        col = mix(vec3(1.), tex, DoG);
        col = mix(vec3(0.), col, DoG);
    }
    if (mode == 3){
        float e1 = eps, e2=2.*eps, e3=4.*eps;
        vec3 tex = texture(BaseTex, uv).rgb;
        float eps1 = tanh(  phi * (DoG - e1)) * texture(Hatch, uv.xy*12.).g;
        float eps2 = tanh(  phi * (DoG - e2)) * texture(Hatch, uv.xy*12.).b;
        float eps3 = tanh(  phi * (DoG - e3)) * texture(Hatch, uv.yx*12.).b;
        float s = eps1 + eps2 + eps3;
        col = eps1 + eps2*(tex) + eps3*tex;
        col /= .5;
    }
    fragColor = vec4(col, 1.);
}
