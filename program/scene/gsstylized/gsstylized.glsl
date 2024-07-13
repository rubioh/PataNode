#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform float energy;
uniform float energy_fast;
uniform float energy_mid;
uniform float energy_slow;
uniform float K;
uniform float bpm;
uniform sampler2D iChannel0;
uniform float mode_flick;
uniform float dkick;


#define PI 3.14159

float dot2(vec2 p){
    return dot(p,p);
}
vec2 hash22(vec2 p){
    vec2 a = vec2(94.86, 43.46);
    vec2 b = vec2(72.67, 13.48);
    p = vec2(dot(p, a), dot(p, b));
    return fract(sin(p*10.29)*48.47);
}

vec3 getH(vec2 uv, float d){
    //uv.x -= .5;
    //uv.x = abs(uv.x) + 10.5; //create linear filtering artifact
    vec2 newc = texture(iChannel0, uv, 0).xy;
    float h =  pow(dot2(1.-newc), d);
    return vec3(uv, h/2.)*1.5;
}
vec3 palette_purple( in float t, float t2 )
{
    vec3 a = vec3(0.4, 0.2, 1.);
    vec3 b = vec3(0.75, 0.7, 0.7);
    vec3 c = vec3(1., 1., 1.);
    vec3 d = vec3(0.6, 0.35, 0.05);

    return a*.2 + .2*b*cos( 6.28318*(c*t*2.+d*t2*.1 + iTime*.00000000001) );
}
vec3 palette_orange(float t, float t2){
  return mix(vec3(.3, .25, .4)*1.5, vec3(.57,.17,.09)/1.4, pow(t2, .125))*(t+.1)*2.;
}


vec3 palette(float t, float t2){
    vec3 purple = palette_purple(t, t2);
    vec3 orange = palette_orange(t, t2);
    return purple * K + orange * (1.-K);
    return mix(purple, orange, .5+.5*cos(iTime/512.));
}

vec3 calcnormal(vec2 p, float d){

    vec2 e = vec2(1.0, -1.0) * 0.001;    
    return normalize(
      e.xyx*getH(p + e.xy, d) +
      e.yxx*getH(p + e.yx, d) +
      e.xxx*getH(p + e.xx, d));
}

vec3 phong(vec3 lightDir, vec3 normal, vec3 rd, vec3 col) {
  // ambient
  vec3 ambient = col*(.5);

  // diffuse
  float dotLN = clamp(dot(lightDir, normal), 0., 1.);
  vec3 diffuse = col * dotLN;

  // specular
  float dotRV = clamp(dot(reflect(lightDir, normal), -rd), 0., 1.);
  vec3 specular = col* pow(dotRV, 16.);

  return ambient + diffuse + (4.*K + 1.*(1.-K))*specular;
}


float getH2(vec2 uv, float d){
    vec2 tex = texture(iChannel0, uv).xy;
    float h = pow(tex.y, d);
    return h;
}

vec3 calcnormal2(vec2 p, float d){

    vec2 e = vec2(1.0, -1.0) * 0.001;    
    return normalize(
      e.xyx*getH2(p + e.xy, d) +
      e.yxx*getH2(p + e.yx, d) +
      e.xxx*getH2(p + e.xx, d));
}

float ring(){

    vec2 p = (gl_FragCoord.xy-.5*iResolution.xy)/iResolution.y;
    float dkick2 = .4+dkick*.0001 +.3*sin(iTime);
    float dc = .2;
    float mask = 1.-(smoothstep(0., dc, abs(length(p)-dkick2)));

    return mask;
}

vec3 getPal3(vec2 uv){
    float d = 32.;
    vec2 tex = texture(iChannel0, uv).xy;
    float h = pow(tex.y, d);
    vec3 data = vec3(tex, h);
    vec3 normal = calcnormal2(uv, d);

    vec3 col = vec3(.0,.5,.7)*(tex.y*4.);
    col += tex.y*ring()*2.*vec3(1., .7, .5);

    vec3 ld = vec3(0.);
    vec3 rd = vec3(uv, -1);
    vec3 ambient = col;

    // diffuse
    float dotLN = clamp(dot(ld, normal), 0., 1.);
    vec3 diffuse = col * dotLN;

    // specular
    float dotRV = clamp(dot(reflect(ld, normal), rd), 0., 1.);
    vec3 specular = col* pow(dotRV, 4.);

    col = ambient + diffuse + specular*energy*2.;

    vec3 colx = vec3(.0, .3, .7)*.2*(data.x+.1);
    return pow(mix(colx, col, data.y/.9), vec3(3., 4., 7.))*(48.)+colx*.1;
}



void main()
{
    vec2 uv = (gl_FragCoord.xy/iResolution.xy);

    float t2 = pow(clamp(getH(uv, 24.).z, 0., 1.), .4);
    vec3 normal = calcnormal(uv, 16.);
    vec3 ld = vec3(.5, .5, 4.5);
    vec3 rd = vec3(uv, getH(uv, 4.).z);
    vec3 col = palette(1.-rd.z, t2);
    col = phong(ld, normal, rd, col);

    if (mode_flick == 0.)
        col = pow(col, vec3(1.5*K + 2.*(1.-K)))*.4;
    else col = getPal3(uv);
    
    col = clamp(col, vec3(0.), vec3(1.));
    fragColor = vec4(col,  1.);
}
