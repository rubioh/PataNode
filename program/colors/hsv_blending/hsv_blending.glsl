#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform sampler2D GradientMap;
uniform float hue_offset;
uniform float saturation_offset;
uniform float value_offset;

#define R iResolution

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

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy;
    
    vec2 st = (.5*R-uv)/R.y*4.;


       // USE VEL OR SATURATION VALUE
    vec2 vel = texture(GradientMap, uv).xy*100.;


    vec3 col = texture(iChannel0, uv/R).rgb;
    col = clamp(col, vec3(0.), vec3(1.));
    float L = length(col/sqrt(3));
    vec3 hsv = rgb2hsv(col);

    float n_hue = noise_perso(vel*.001+iTime*.000001 + noise_perso(vec2(pow(hsv.z, 1.) + st/40.)*5. + iTime*.000001)*4. + st*.05);
    n_hue = noise_perso(n_hue*n_hue*20.+vec2(0.));
    float n_sat = noise_perso(vel + 10.);
    float n_val = noise_perso(vel + 5.);

    hsv.x += hue_offset + (cos(n_hue*n_hue + iTime*.01)*.5+.5)*.2 + .5;//
    hsv.y += saturation_offset+.1 + n_hue*n_hue*.4;//
    hsv.z += value_offset;//

    vec3 rgb = hsv2rgb(hsv);
    rgb = clamp(rgb, vec3(0.), vec3(1.)) * smoothstep(.0, .05, L);
    fragColor = vec4(rgb, 1.0);

}
