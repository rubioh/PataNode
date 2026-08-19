#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float hue_offset;
uniform float saturation_offset;
uniform float value_offset;
uniform float dry_wet;

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
void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy;

    vec3 col = texture(iChannel0, uv/R).rgb;
    // The untouched input, captured before this shader works on it:
    // the dry end of dry_wet must be a true bypass.
    vec3 dry = col;
    col = clamp(col, vec3(0.), vec3(1.));
    float L = length(col/sqrt(3));
    vec3 hsv = rgb2hsv(col);

    hsv.x += hue_offset;//
    hsv.y += saturation_offset;//
    hsv.z += value_offset;//

    vec3 rgb = hsv2rgb(hsv);
    rgb = clamp(rgb, vec3(0.), vec3(1.)) * smoothstep(.0, .05, L);
    fragColor = vec4(mix(dry, rgb, dry_wet), 1.0);

}
