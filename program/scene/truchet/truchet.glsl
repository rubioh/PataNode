#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform float iTime;
uniform float energy_fast;
uniform float energy_slow;
uniform float bpm;
uniform float angle_rot;
uniform float intensity;
uniform float vitesse;
uniform float trigger;
uniform float deep;
uniform vec3 color;
uniform sampler2D iChannel1;
uniform float K;
uniform float smooth_low;
uniform float accum_rot;

const int MAX_MARCHING_STEPS = 25;
const float MIN_DIST = 0.0;
const float MAX_DIST = 20.0;
const float PRECISION = 0.003;

#define PI 3.14159265359



// iq's distance function
// https://iquilezles.org/articles/distfunctions/
float opExtrusion (vec3 p, float d, float h)
{
    vec2 w = vec2( d, abs(p.z) - h );
    return min(max(w.x,w.y),0.0) + length(max(w,0.0));
}
vec3 palette(float t, vec3 a, vec3 b, vec3 c, vec3 d )
{
    return a + b*cos(6.28318*(c*t+d));
}

mat2 rotation(float angle){
    return mat2(cos(angle), sin(angle), -sin(angle), cos(angle));
}

vec2 hash( vec2 p )
{
    //p = mod(p, 4.0); // tile
    p = vec2(dot(p,vec2(175.1,311.7)),
             dot(p,vec2(260.5,752.3)));
    return fract(sin(p+455.)*18.5453);
}

float hash11(float i)
{
    return fract(sin(i*455.55+17.546)*18.5453);
}

vec3 hash13(float p){
    vec3 x = vec3(p*17.256, mod(p, 32.659)*14.456, mod(p, 135.235)*17.235);
    return fract(sin(x)*vec3(8.5453, 11.2378, 11.5678));
}


float hash31(vec3 p){
    float x = mod(dot(p, vec3(17256, 14.23, 8.2)), 32.659)*23.12;
    return fract(sin(x)*17.26877);
}


vec2 hash2( vec2 p )
{
    const vec2 k = vec2( 0.3183099, 0.3678794 );
    float n = 111.0*p.x + 113.0*p.y;
    return fract(n*fract(k*n));
}

float noise(in vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    float a = hash2(i).x;
    float b = hash2(i + vec2(1.0, 0.0)).x;
    float c = hash2(i + vec2(0.0, 1.0)).x;
    float d = hash2(i + vec2(1.0, 1.0)).x;
    vec2 u = f*f*(3.0-2.0*f);

    return mix(a, b, u.x) +
            (c - a)* u.y * (1.0 - u.x) +
            (d - b) * u.x * u.y;
}

float fbm( in vec2 x)
{
    float t = 0.0;
    float amp = 0.;
    for( int i=1; i<2; i++ )
    {
        float f = pow( 2., float(i) );
        float a = pow( f, -.75 );
        amp = 10.*step(3., float(i));
        t += a*noise(f*x+amp);
    }
    return t*1.-.4;
}

vec3 ground(vec2 uv){
    vec3 a = vec3(0.5, 0.5, 0.5);
    vec3 b = 1.-a;
    vec3 c = vec3(.3, .3, .3);
    vec3 d = vec3(0.0, 0.1, 0.2);
    uv = uv/4.;
    float tmp = fbm(uv+fbm(uv+length(uv)-iTime));

    return palette(tmp, a,b,c,d);


}

float sdPlane( vec3 p, vec3 n, float h )
{
  // n must be normalized
  vec2 uv = p.xy/4.;
  return dot(p,n) + h;
}

mat2 rot(float angle){
    return mat2(cos(angle), sin(angle), -sin(angle), cos(angle));
}

float len(vec2 uv, vec2 UV){
    float N = 1.5+.5*cos(iTime/128. + cos(iTime/313.)*2.*(.5+.5*smooth_low)*(noise(uv)-.5)*3.14159);
    return pow(pow(abs(uv.x), N) +  pow(abs(uv.y), N), 1./N);
}

float flip(vec2 v, float w)
{
    v = fract(v/2.)-.5;
    return mix(w, 1. - w, step(0., v.x * v.y));
}

float truchet(vec2 coord, vec2 UV){
    float l = smoothstep(.45, .55, abs(len(coord, UV)));
    l *= smoothstep(.45, .55, abs(len(coord-1., UV)));
    return l;
}

float truchet_border(vec2 coord, float width, vec2 UV){
    float l = smoothstep(0., .1, abs(len(coord, UV)-.5) - width);
    l *= smoothstep(0., .1, abs(len(coord-1., UV)-.5) - width);
    return l;
}

float pattern_in(vec2 v)
{
    vec2 id = floor(v);
    vec2 coord = fract(v);
    return
        flip(v, hash(id).x < .5 ? 1.-truchet(coord, v) : truchet(vec2(1.-coord.x,coord.y), v));
}

float pattern_border(vec2 v, float width, inout vec3 col, inout float ID, float idZ)
{
    vec2 id = floor(v);
    vec2 coord = fract(v);
    //float touch = hash(id).x < .5 ? truchet_border(coord, width) : truchet_border(vec2(1.-coord.x,coord.y), width);

    vec4 truchet = texelFetch(iChannel1, ivec2(id)+20, 0);
    vec3 connex = truchet.rgb;

    float touch = connex.z < .5 ? truchet_border(coord, width, v) : truchet_border(vec2(1.-coord.x,coord.y), width, v);

    //ID = .5;

    col = (1.-touch)*vec3(1.);

    if (connex.z> .5){
        if (coord.x<coord.y){
            col *= hash13(connex.y + idZ);
            ID = connex.y;}
        else {
            col *= hash13(connex.x + idZ);
            ID = connex.x;}
    }
    if (connex.z<.5){
        if (1.-coord.y<coord.x){
            col *= hash13(connex.y + idZ);
            ID = connex.y;}
        else {
            col *= hash13(connex.x + idZ);
            ID = connex.x;}
    }
    ID += K + idZ;
    return touch;
}

#define R iResolution

vec4 SDF (vec3 p, inout float id)
{
    float d = 1e10;
    vec3 col = vec3(0.,0.,0.);
    p.z -= deep*.5;

    float width = .05*(.1+energy_fast*4.);
    float per = 3.1415*3.;
    vec3 fcol = vec3(.0);
    vec3 tmp_p = p;
    tmp_p.z = mod(p.z, per)-per*.5;
    float idZ = floor((p.z)/per);
    float v_r = hash11(idZ)*.5-1.;
    tmp_p.xy *= rotation(idZ*1.2 + v_r*(accum_rot+sign(v_r)*iTime*.1)*.05);

    float L = length((p.xy-.5)*R/R.y);
    L = 1./(2.*sqrt(L)+3.);
    float dt = opExtrusion(tmp_p, pattern_border(tmp_p.xy*(.3+energy_slow), width, col, id, idZ), .2);
    if (dt<d){
        fcol = col*L*4.;
        d = dt;
    }
    return vec4(d, fcol);
}


vec3 calcNormal(vec3 p) {
    vec2 e = vec2(1.0, -1.0) * 0.002; // epsilon
    float r = 1.; // radius of sphere
    float osef = 0.;
    return normalize(
      e.xyy * SDF(p + e.xyy, osef).x +
      e.yyx * SDF(p + e.yyx, osef).x +
      e.yxy * SDF(p + e.yxy, osef).x +
      e.xxx * SDF(p + e.xxx, osef).x);
}

vec4 rayMarch(vec3 ro, vec3 rd, float start, float end, inout float id) {
  float depth = start;
  vec3 col;
  float tmp_id = .0;
  //float precision_ = PRECISION*length(rd.xy);
  float LRD = length(rd.xy);
  float precision_ = .01*LRD*5.;
  float dit = fract(sin(dot(rd, vec3(17.234, 27.2378, 23.5645))*17.5687)*74.587)*.1;
  for (int i = 0; i < MAX_MARCHING_STEPS; i++) {
    vec3 p = ro + (depth+dit) * rd;
    vec4 d = SDF(p, tmp_id);
    depth += max(abs(d.x)*.4, sign(d.x)*precision_*2.);
    if (abs(d.x) < precision_ || depth > end){
        col = d.yzw;
        if (d.x < precision_) id = tmp_id;
        else id = .01;
        break;}
  }
  return vec4(depth, col);
}

vec3 phong(vec3 lightDir, vec3 normal, vec3 rd, vec3 col) {
  // ambient
  vec3 ambient = col*(.5+.5*normal.y);

  // diffuse
  float dotLN = clamp(dot(lightDir, normal), 0., 1.);
  vec3 diffuse = col * dotLN;

  // specular
  float dotRV = clamp(dot(reflect(lightDir, normal), -rd), 0., 1.);
  vec3 specular = 3.*col * pow(dotRV, 5.);

  return ambient + diffuse + specular;
}



void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;
    vec2 uv_tmp = uv;
    vec3 col;


    float angle = angle_rot;
    mat2 rot = rotation(angle*.0000001);

    uv = rot*uv;
    uv *= (1.+energy_fast*.2);

    vec3 ro = vec3(0, 0, 3); // ray origin that represents camera position
    vec3 rd = normalize(vec3(uv, -1.5)); // ray direction

    float id = 0.;
    vec4 d = rayMarch(ro, rd, MIN_DIST, MAX_DIST, id); // distance to sphere
    vec3 backgroundColor = vec3(0.);
    float lum = .0;
    if (d.x > MAX_DIST) {
        col = backgroundColor; // ray didn't hit anything
        lum = .0;
        } else {

        vec3 p = ro + rd * d.x; // point on sphere we discovered from ray marching
        vec3 normal = calcNormal(p);
        vec3 lightPosition = vec3(2, 2, 7);
        vec3 lightDirection = normalize(lightPosition - p);
        float lint = 1.2;
        lum = pow(hash11(id)*1.1, 16.);
        col = lint*phong(lightDirection, normal, rd, d.yzw)*(lum*.8+.2);

    }
    float LU = length(uv_tmp*iResolution.y/iResolution.xy);
    col *= 1./(1.+LU*LU*5.);
    fragColor = vec4(clamp(col, vec3(0.), vec3(1.))*1., lum*15.* pow(smooth_low, .25));
}
