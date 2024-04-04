#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform sampler2D iChannel0;
uniform float dry_wet;
uniform float nrj;

#define read(uv, offset) clamp(texture(iChannel0, uv+offset/iResolution).rgb, vec3(-1.), vec3(1.))

vec3 sobel(vec2 uv){

    vec3 s00 = read(uv, vec2(0.));
    vec3 s01 = read(uv, vec2(0., 1.));
    vec3 s10 = read(uv, vec2(1., 0.));
    vec3 s11 = read(uv, vec2(1., 1.));
    vec3 s11m = read(uv, vec2(1., -1.));
    vec3 s1m1 = read(uv, vec2(-1., 1.));
    vec3 s01m = read(uv, vec2(0., -1.));
    vec3 s1m0 = read(uv, vec2(-1., 0.));
    vec3 s1m1m = read(uv, vec2(-1., -1.));
    
    vec3 Gx = -s1m1 - 2.*s1m0  - s1m1m + s11 + 2.*s10 + s11m;
    vec3 Gy = -s1m1 - 2.*s01  - s11 + s1m1m + 2.*s01m + s11m;
    return sqrt(Gx*Gx + Gy*Gy);
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    vec3 col = sobel(uv);

    col = col*(1-nrj*dry_wet) + read(uv, vec2(0.))*(nrj*dry_wet*2.);
    col = clamp(col, vec3(0.),vec3(1.));

    fragColor = vec4(col,1.0);

}
