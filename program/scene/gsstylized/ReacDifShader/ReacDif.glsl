#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
//uniform int iFrame;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform float f;
uniform float k;
uniform float Db;
uniform float Da;
uniform float on_kick;
uniform vec2 center;
uniform float radius_triangle;

#define dt 1.
#define PI 3.14156
#define s(x, y, sampler) texture(sampler, (gl_FragCoord.xy+vec2(x,y))/iResolution.xy).xy
//#define s(x, y, sampler) texelFetch(sampler, ivec2(gl_FragCoord.xy)+ivec2(x,y), 0).xy

vec2 p2(vec2 p){
    return (p*p);
}
vec2 Laplacian(vec2 center, sampler2D Chan){

    vec2 L = vec2(0.);

    vec2 v00 = .5*s(-1, 1, Chan),  v10 = s(0, 1, Chan), v20 = .5*s(1, 1, Chan),
         v01 = s(-1, 0, Chan),                       v21 = s(1, 0, Chan),
         v02 = .5*s(-1,-1, Chan),  v12 = s(0,-1, Chan), v22 = .5*s(1,-1, Chan);

    return (v10 + v01 + v21 + v12 + 0.*(v00 + v20 + v02 + v22) -  4. * center);
}

float Triangle(){

    vec2 uv = (gl_FragCoord.xy-.5*iResolution.xy)/iResolution.y;

    uv *= 3.*radius_triangle;
    uv.y += .5;
    int N = 3;

    // Angle and radius from the current pixel
    float a = atan(uv.x,uv.y)+PI;
    float r = 2.*PI/float(N);

    // Shaping function that modulate the distance
    float d = cos(floor(.5+a/r)*r-a)*length(uv);

    return smoothstep(.8, 1., d)*.01;
}

float circle(vec2 uv){
    uv = (uv-.5*iResolution.xy)/iResolution.y;
    float mask = smoothstep(0., .7+radius_triangle/10., abs(length(uv)));
    return mask*.01;
}

void main()
{

    vec2 uv = gl_FragCoord.xy;
    float t = iTime;
    vec2 center = s(0, 0, iChannel0);

    vec2 L = Laplacian(center, iChannel0) + .000001*cos(iTime+iResolution.x);

    float len = smoothstep(.4, .1, length((gl_FragCoord.xy*2.-iResolution.xy)/iResolution.y));
    float f1 = mix(0.026, f, len);
    float k1 = mix(0.051, k, len);

    float a = center.x;
    float b = center.y;
    float da = (L.x*Da - a*b*b + f1*(1.-a))*dt;
    float db = (L.y*Db + a*b*b - (k1+f1)*b)*dt;

    float na = a +da;
    float nb = b +db;

    if (on_kick != 0.){
        nb += circle(uv);
        //nb += Triangle();//*.0000001;

    }

    na = clamp(na, 0., 1.);
    nb = clamp(nb, 0., 1.);

    vec2 state = vec2(na, nb);
    fragColor = vec4(state.xyxy);

    //fragColor = vec4(state.xyxy);
        
}
