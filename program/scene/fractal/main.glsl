#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform float energy;
uniform float energy_fast;
uniform float energy_slow;
uniform float bpm;
uniform float sens;
uniform float angle_rot;
uniform float deep;
uniform float n_spiral;
uniform float decaying_kick_slow;
uniform float face;
uniform float t;
uniform float t_high;
uniform float K;


// Primitive shape for the right l-system.

#define PI 3.14159

vec2 cmul(vec2 a, vec2 b){
    return vec2(a.x*b.x-a.y*b.y, a.x*b.y+a.y*b.x);
}


vec2 cinv(vec2 a){
    float l = length(a);
    l = l*l;
    return vec2(a.x, -a.y)*l;
}

vec2 cdiv(vec2 a, vec2 b){
    b = cinv(b);
    return cmul(a, b);
    
}

vec2 ma_fonction(vec2 p){
    vec2 b = vec2(-.340+energy/300., .630) + .001*vec2(cos(2.), sin(2.))+ .5*vec2(cos(iTime/64.), sin(iTime/256.)) + 0.07*vec2(cos(iTime/256+1.)*2., -sin(iTime/32.+2.));
    p = cmul(p, p) + b;
    return p;
}

vec4 tree(vec2 uv){
    vec2 p = uv;
    vec4 dmin = vec4(1000.);
    float N = 2+K;

    for (float i=0.; i<N; i++){
        p = ma_fonction(p);
        dmin=min(dmin, vec4(abs(cos(energy*.75+iTime*.1)*.3+p.y + 0.5*sin(p.x)), 
                        abs(energy_fast/50.+.5+p.x + 0.5*sin(p.y+t_high)), 
                        dot(p,p)*(1.+energy_fast/2.),
                        length(fract(p)-.5)  ));
                        //fract(length(p)-.5)  ));
    }
    return dmin;
}

vec2 stop2(vec2 uv){
    vec2 p = uv;
    float dmin = 1000.;
    float dmin2 = 1000.;
    for (float i=0.; i<2.; i++){
        p = ma_fonction(p);
        if (i==1){
            dmin=min(dmin, abs(sin(p.x+iTime/32.+2*PI*decaying_kick_slow*1.)+sin(p.y+2*PI*decaying_kick_slow)*(length(p))));
        }
        else{
             dmin2 = min(dmin2,
                        length(fract(p)-.5));
        }
    }
    return vec2(dmin, dmin2);


}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;
    vec2 st = uv;


    //uv /= 2.;
    //uv += vec2(.355, -.375);
    float angle = t;
    mat2 rot = mat2(cos(angle), sin(angle), -sin(angle), cos(angle));
    uv = uv;

    // Time varying pixel color
    vec4 dmin = (tree(uv));
    float tmp = dmin.w;
    vec2 stop = stop2(uv);
    dmin.w = stop.x;
    
    dmin.x = 1.-smoothstep(-.1, .1, dmin.x);
    dmin.x = pow(dmin.x*3., 1.+1.*energy_slow);

    dmin.y = stop.y;
    
    fragColor = vec4(dmin);
}
