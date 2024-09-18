#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform float energy_fast;
uniform float t_h;
uniform float count_beat;
uniform float thresh;
uniform float t_rot;

#define PI 3.14159265359


#define saturate(v) clamp(v,0.,1.)
#define aa (vec3(.7, .7, .7) + vec3(.3*cos(iTime*.01*.7*.25), .3*cos(.25*iTime*.017*.5), .3*cos(iTime*.021*.2)))*.5
#define bb vec3(.4, .4, .4)
#define cc vec3(.7, .6, 1.3)*.5
#define dd vec3(0.6, 0.35, .05)

float hash21(vec2 p){
    vec2 d = vec2(137.247687,274.578964);
    float k = dot(p,d);
    return fract(sin(k*17.2746)*11.5473);
}



float cross_(vec2 a, vec2 b){
    return a.y*b.x-a.x*b.y;
}

vec3 palette(float t, vec3 a, vec3 b, vec3 c, vec3 d )
{
    return a + b*cos(6.28318*(c*t+d));
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
vec3 hsv2rgb(vec3 c){
    vec4 K=vec4(1.,2./3.,1./3.,3.);
    return c.z*mix(K.xxx,saturate(abs(fract(c.x+K.xyz)*6.-K.w)-K.x),c.y);
}

vec4 make_square_cell(vec2 coord, vec2 index){
    

    vec2 centered_coord = coord-.5;
    //float angle = iTime*.4;
    //centered_coord *= mat2(cos(angle), sin(angle), -sin(angle), cos(angle));
    float length_ = max(abs(centered_coord.x), abs(centered_coord.y));
    float radius = energy_fast*.7;
    float square1 = max(abs(centered_coord).x, abs(centered_coord).y);
    float square = 1.-smoothstep(0., 0.02, square1-radius);

    radius = .1;
    float csquare = 1.-smoothstep(0., 0.02, abs(square1-radius)-.0025);


    float id = hash21(index + vec2(count_beat, count_beat*.1+index.y*.5));
    float go_id = step(thresh, id);

    vec3 col_square = palette(cos(iTime/4.*.05 + (id-.5)*.5), aa,bb,cc,dd)*.7*go_id*square;
    if (go_id == 0){
        col_square = palette(cos(iTime/4.*.05+ .5*3.14159*id), aa,bb,cc,dd)*csquare*.5;
    }


    return vec4(col_square, square);
}



mat2 rotation_matrix(float angle){
    return mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
}



void main()
{
    // Normalized pixel coordinates (from 0 to 1)

    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;

    uv /= 3;
    mat2 rot = rotation_matrix(iTime/8.);
    uv = rot*uv;

    float N = 5.+(cos(t_rot/32))*2.;

    vec2 uvp = uv;
    uv *= vec2(N, N)*vec2(N, N);
    uv = sqrt(abs(uv));

    float mask = sqrt(length(uv.x))*sqrt(length(uv.y));

    float m2 = min(abs(uvp.x), abs(uvp.y));
    mask = pow(m2*2., .5)*2.;

    rot = rotation_matrix(t_h*.33);
    uv = rot*uv;

    //uv = sqrt(abs(uv));

    // Time varying pixel color


    vec4 cell = make_square_cell(fract(2.*uv), floor(2.*uv));
    // Output to screen
    vec3 col = cell.rgb*mask;

    fragColor = vec4(col, 1.0);
}
