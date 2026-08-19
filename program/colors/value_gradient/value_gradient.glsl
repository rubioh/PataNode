#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float frequency;
uniform float phase_r;
uniform float phase_g;
uniform float phase_b;
uniform float saturation;
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
    vec2 uv = gl_FragCoord.xy;
    vec3 col = texture(iChannel0, uv / R).rgb;
    // The untouched input, captured before this shader works on it:
    // the dry end of dry_wet must be a true bypass.
    vec3 dry = col;

    // Clamped because the FBOs are f4: an upstream Bloom or Tone Mapping
    // can deliver channels outside [0,1], and this value is used twice --
    // to index the palette and as the output brightness.
    float v = clamp(rgb2hsv(col).z, 0.0, 1.0);

    vec3 palette = 0.5 + 0.5 * cos(6.28318530718 *
        (frequency * v + vec3(phase_r, phase_g, phase_b)));

    // Only hue and saturation come from the palette; v goes back in as
    // brightness so the input's relief survives.
    vec3 palette_hsv = rgb2hsv(palette);
    vec3 rgb = hsv2rgb(vec3(palette_hsv.x, palette_hsv.y * saturation, v));

    fragColor = vec4(mix(dry, clamp(rgb, vec3(0.), vec3(1.)), dry_wet), 1.0);
}
