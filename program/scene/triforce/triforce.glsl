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

float line(vec2 uv, vec2 line, float l) {

float k = dot(uv, line) / dot(line, line);
vec2 pp = uv + line * k;
    return smoothstep(0.01, 0.0, length(pp-uv)) * 
    smoothstep(0.01, 0.00, length(pp) - l) ;
}

float triangle(vec2 uv) {
float sin_60_degree = 0.5;
float cos_60_degree = 0.86602540378;

float l = .289;
float d = .145;//l / 1.52;
float kk = .31;
       float c = line(uv + vec2(-d, kk), normalize(vec2(cos_60_degree, sin_60_degree)), l );
    c = max(c, line(uv + vec2(d, kk), normalize(vec2(-cos_60_degree, sin_60_degree)), l ));
   
   c = max(c,  line(uv + vec2(.0, .56), normalize(vec2(0., 1.)),l ));
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
     float c = triangle(uv + vec2(-dd,0));
     c = c + triangle(uv + vec2(dd, 0.));
     c = c + triangle(uv + vec2(0., dy));
 
 fragColor = vec4(c,c,c,1. + 0.1 * (energy_fast + energy_mid + energy_slow + bpm + intensity + tf + scale + iTime));
}