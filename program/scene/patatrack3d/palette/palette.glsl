#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float iTime;
uniform float th;
uniform float ts;
uniform float energy;
uniform float on_kick;
uniform float mode_ptt;
uniform float thp;
#define R iResolution

float sdBox( in vec2 p, in vec2 b )
{
    vec2 d = abs(p)-b;
    return length(max(d,0.0)) + min(max(d.x,d.y),0.0);
}

vec3 palette(float t){
    vec3 a = vec3(0.204,0.396,0.643);
    vec3 b = vec3(0.361,0.208,0.400);
    vec3 c = vec3(1., 1., 1.);
    vec3 d = vec3(0.961,0.475,0.000)*.1;
    return a + b*cos( 6.28318*(c*t+d) );
}
float rand( vec2 p ) {
    return fract(sin( dot(p,vec2(3217.1,1341.7)))*95.53);
}
float noise(vec2 p){
    vec2 fr = fract(p);
    vec2 fl = floor(p);

    float r1 = rand(fl);
    float r2 = rand(fl + vec2(1., 0.));
    float r3 = rand(fl + vec2(0., 1.));
    float r4 = rand(fl + vec2(1., 1.));

    vec2 t = smoothstep(0.,1.,fr);

    return mix(mix(r1, r2, t.x), mix(r3, r4, t.x), t.y);
}

mat2 rotate(float a){
    float ca=cos(a), sa=sin(a);
    return mat2(
        ca, -sa,
        sa,  ca
    );
}
float smooth_floor(float x){
    float m = fract(x);
    return floor(x) + (pow(m, 20.) - pow(1.-m, 20.) )/2.;
}
vec3 palette2(float t){
    vec3 a = vec3(0.161,0.208,0.400);
    vec3 b = vec3(0.125,0.290,0.529);
    vec3 c = vec3(1.000,1.000,1.000);
    vec3 d = vec3(0.1,0.2,0.3)*.1;
    return a + b*cos( 6.28318*(c*t+d) );
}
vec3 getStars(vec2 uv){
    float t = -ts;
    uv *= 1. + .5*cos(th*1.124);
    uv *= rotate(.5*t - log(20.*length(uv)));

    float lacunarity = 2.0;
    float gain = .6;

    float amplitude = 0.4;
    float frequency = 1.;

    float n = 0.;

    for(int i =0; i<6; i++){
        n += amplitude * noise(frequency*uv);
        frequency *= lacunarity;
        amplitude *= gain;
    }
    float val = 20.*n + .9 * t;
    float sm_val = smooth_floor(val)*.1;
    float dsm_val = smooth_floor(val + (.01 + .1*energy))*.1;
    float diff = abs(sm_val - dsm_val)*10.;
    return palette2(sm_val*2.)*(.05+2.*energy*diff);
}

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution.xy;
    vec2 uvE = (gl_FragCoord.xy*2.-iResolution.xy)/iResolution.y;
    vec4 res = texture(iChannel0, uv+vec2(.5)/iResolution.xy).rgba;

    vec2 shift = vec2(-.7-.2*cos(th),-1.8-1.*cos(th));
    float eye = sdBox(uvE*5. + shift, vec2(.01,.08 + .02*cos(th) ));
    eye = min(eye, sdBox(uvE*5.+shift*vec2(-1.,1.), vec2(.01,.08+ .02*cos(th) )));
    eye = smoothstep(.02, .0, eye-.05);


    vec3 col = pow(palette(res.y*.4-iTime)*.8+.2, vec3(2.))*res.x;

    vec3 stars = vec3(0.);
    vec3 col_s = vec3(.0);
    if (res.z == 1.){
        float depth = abs(res.a-3.8);
        float LD = 1./(1.+depth*depth*100.);
        stars = getStars(uvE);
        col_s += clamp(stars, vec3(0.), vec3(10.)) * exp(-LD*LD*8.);
    }
    col = col + eye*palette(res.x * .4 -iTime);
    col = mix(vec3(.0), col, mode_ptt);
    fragColor = vec4(col_s + col, max(res.x, max(eye, length(stars)*1.)));
}
