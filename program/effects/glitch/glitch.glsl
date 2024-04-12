#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float energy_low;
uniform float sens;
uniform float mode;
uniform vec2 translate;
uniform float camp;

#define R iResolution

mat2 rot2d(float a){
    return mat2(cos(a), sin(a), -sin(a), cos(a));
}

float mask(vec2 uv){
    return step(0, uv.x)*step(uv.x, R.x)*step(0, uv.y)*step(uv.y, R.y);
}
vec3 rgb2hsv(vec3 c)
{
    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));

    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c)
{
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}
void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy;

    mat2 rotg = rot2d(0.);
    mat2 rotb = rot2d(0.);
    float C = camp*2.+.5;
    if (mode == 0){
        rotg = rot2d(C*energy_low*sens*.2);
        rotb = rot2d(-C*energy_low*sens*.2);
    }

    vec2 tb = vec2(0.);
    vec2 tr = vec2(0.);
    if (mode == 1){
        tb = translate*C*energy_low*.2;
        tr = -translate*C*energy_low*.2;
    }

    float sr = 1.;
    float sg = 1.;
    if (mode == 2){
        sr = (1.-energy_low*C*.2);
        sg = (1.+energy_low*C*.2);
    }

    vec2 uvr = sr*(uv-.5*R)+tr + .5*R;
    vec2 uvg = sg*((uv-.5*R)*rotg)+.5*R;
    vec2 uvb = ((uv-.5*R)*rotb)+tb+.5*R;

    float t = iTime*.001;
    float phi1 = mod(360.+t, 360.);///360.*2.*3.14159;
    float phi2 = mod(120.+t, 360.);///360.*2.*3.14159;
    float phi3 = mod(240.+t, 360.);///360.*2.*3.14159;

    vec3 r = vec3(0.);
    r.rgb = mask(uvr)*texture(iChannel0, uvr/R).rgb;
    r.gb *= 0.;
    r = hsv2rgb(rgb2hsv(r) + vec3(phi1,0.,0.));

    vec3 g = vec3(0.);
    g.rgb = mask(uvg)*texture(iChannel0, uvg/R).rgb;
    g.rb *= 0.;
    g = hsv2rgb(rgb2hsv(g) + vec3(phi2,0.,0.));

    vec3 b = vec3(0.);
    b.rgb = mask(uvb)*texture(iChannel0, uvb/R).rgb;
    b.rg *= 0.;
    b = hsv2rgb(rgb2hsv(b) + vec3(phi3,0.,0.));

    fragColor = vec4((r+g+b),1.0);

}
