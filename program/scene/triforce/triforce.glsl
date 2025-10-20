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
uniform vec3 d11;
uniform vec3 d12;
uniform vec3 d13;
uniform vec3 d21;
uniform vec3 d22;
uniform vec3 d23;
uniform vec3 d31;
uniform vec3 d32;
uniform vec3 d33;


float line(vec2 uv, vec2 line, float l) {

float k = dot(uv, line) / dot(line, line);
vec2 pp = uv + line * k;
    return smoothstep(0.01, 0.0, length(pp-uv)) * 
    smoothstep(0.01, 0.00, length(pp) - l) ;
}

vec3 triangle(vec2 uv, mat3 ddd) {
    float sin_60_degree = 0.5;
    float cos_60_degree = 0.86602540378;

    float l = .289;
    float d = .145;//l / 1.52;
    float kk = .31;
    vec3 c = ddd[1] * line(uv + vec2(-d, kk), normalize(vec2(cos_60_degree, sin_60_degree)), l );
    c = c +  ddd[0] * line(uv + vec2(d, kk), normalize(vec2(-cos_60_degree, sin_60_degree)), l );   
    c = c + ddd[2] * line(uv + vec2(.0, .56), normalize(vec2(0., 1.)),l );
    return c;
}

void main()
{

    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;
    uv.y -= .05;
//    float c = smoothstep(.41, .42, length(uv));
float dd = .295;
float dy = -.51;
//float c = triangle(uv);
     vec3 c = triangle(uv + vec2(-dd,0), mat3(d31, d32, d33));
     c = c + triangle(uv + vec2(dd, 0.), mat3(d11, d12, d13));
     c = c + triangle(uv + vec2(0., dy), mat3(d21, d22, d23));
 
 fragColor = vec4(c,1. + 0.1 * (d11 + energy_fast + energy_mid + energy_slow + bpm + intensity + tf + scale + iTime));
}