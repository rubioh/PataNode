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



vec3 palette(float t, vec3 a, vec3 b, vec3 c, vec3 d )
{
    return a + b*cos(6.28318*(c*t+d));
}

vec2 hash( vec2 p )
{
    //p = mod(p, 4.0); // tile
    p = vec2(dot(p,vec2(175.1,311.7)),
             dot(p,vec2(260.5,752.3)));
    return fract(sin(p+455.)*18.5453);
}

vec2 hash2( vec2 p ) 
{
    const vec2 k = vec2( 0.3183099, 0.3678794 );
    float n = 111.0*p.x + 113.0*p.y;
    return fract(n*fract(k*n));
}
float noise_perso(in vec2 st) {
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
    for( int i=1; i<7; i++ )
    {
        float f = pow( 2., float(i) );
        float a = pow( f, -.75 );
        amp = pow(energy_mid*4., 1.5)*step(3., float(i));
        t += amp*a*noise_perso(f*x+amp+tf);
    }
    return t*1.-.4;
}

vec2 make_eye(vec2 uv){
    float area_eye = smoothstep(80./iResolution.y, 0., abs(abs(uv.y)-0.1 - (.15+energy_slow*1.2+energy_fast/3.)*sin(uv.x+PI/2.))-.02);
    return vec2(area_eye, // contour
              smoothstep(140./iResolution.y, 0., abs(uv.y) - (.15+energy_slow*1.2+energy_fast/3.)*sin(uv.x+PI/2.))// inside
            );
}

vec2 make_pupil(vec2 uv, vec2 center, float radius){
    return vec2(
        smoothstep(5./iResolution.y, 0., abs(length(uv+-center)-radius)-.02), // Pupille contour
        1.-smoothstep(-5./iResolution.y, 0., (length(uv-center)-radius)-.02)); // Pupille inside
}


void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;

    uv *= 1.8;
    // Time varying pixel color
    vec2 center = vec2(0., 0.);
    float radius = .05+energy_fast/2.;
    
    vec2 pupille = make_pupil(uv, center, radius);
    vec2 eye = make_eye(uv);
    
    vec2 st = (uv-center)*(3.);
    float N = 2;
    float length_st = pow(pow(abs(uv.x), N) + pow(abs(uv.y), N), 1/N);
    float n = noise_perso(vec2(length_st, length_st)*2. - iTime*.33)*intensity+fbm(abs(st/scale)-tf+fbm(abs(st/scale)))*intensity/4 ;
    vec3 a = vec3(0.5, 0.5, 0.5);
    vec3 b = 1.-a;
    vec3 c = vec3(1., 1., 1.);
    vec3 d = vec3(0.0, 0.1, 0.2);
    vec3 iris = palette(n*.7, a,b,c,d)*eye.y* (1. - pupille.y);
    
    vec3 col = iris + eye.x*vec3(.5)+pupille.x*vec3(.5);
    // Output to screen
    fragColor = vec4(col,1.0);
}

