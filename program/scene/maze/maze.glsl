#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform float energy_fast;
uniform float energy_mid;
uniform float energy_slow;
uniform float bpm;
uniform float intensity;
uniform float tf;
uniform float scale;
#define PI 3.141593

mat2 ro(float a) {
    return mat2(cos(a), -sin(a), sin(a), cos(a));
}

float time() {
    return iTime / 10.;
}
float sp(vec3 pp) {
float ret = 0.;
for (int i = 0; i < 1; ++i) {
vec3 p = pp;
float rz = 5.;
float aa = floor((p.z + 13.*time()) * rz);
float tt = mix(.3, 1.9, 1.+.5*sin(time() / 2.) );;
tt = 2.1;
//p.y += sin(p.z / 100.) * 2.5;
p.z = mod(p.z + 13.*time(), rz) - rz / 2.;
    p.z -= 2.5;
        p.xy *= ro(aa / 12. + tt / 2. + (pp.z + time() * 13.) * 1.3);

    float rx = .3;
    p.x = mod(p.x, rx) - rx / 2.;
    p.y = abs(p.y);
//    p.y -= 1.9;
    p.y -= tt;
    ret += (length(p) + .01);
    }
    return ret;

}
float map(vec3 p) {
    return min(sp(p), sp(p.xyz));
}


float rm(vec3 ro, vec3 rd) {
    float t = 0.;
    float ret = .0;
    for (int i = 0; i < 180;++i) {
        vec3 p = ro + rd * t;

        float d = map(p);
        t += d * .35;
        ret += .0025/d;//smoothstep(.1, .0, d);
    }
    return ret;
}

void main()
{
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;
    
    vec3 rd = normalize(vec3(uv, 1.));
    // Time varying pixel color
    float c = rm(vec3(0.), rd);
    
    vec3 col = vec3(c * 2., c, c * 2. + .2*sin(time()) );//vec3( .2*sin(c * 5.+ time() * 1.), c, c  );

    // Output to screen
    fragColor = vec4(col * 1.5,1. + 0.01 * (energy_fast + energy_mid + energy_slow + bpm + intensity + tf + scale + time()));
}