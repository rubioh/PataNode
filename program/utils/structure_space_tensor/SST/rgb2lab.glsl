#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform sampler2D iChannel0;
#define R iResolution
#define PI 3.1415

vec3 rgb2xyz(vec3 c) {
    vec3 tmp;

    tmp.x = (c.r > 0.04045) ? pow(abs((c.r + 0.055) / 1.055), 2.4) : c.r / 12.92;
    tmp.y = (c.g > 0.04045) ? pow(abs((c.g + 0.055) / 1.055), 2.4) : c.g / 12.92,
    tmp.z = (c.b > 0.04045) ? pow(abs((c.b + 0.055) / 1.055), 2.4) : c.b / 12.92;

    const mat3 mat = mat3(
        0.4124, 0.3576, 0.1805,
        0.2126, 0.7152, 0.0722,
        0.0193, 0.1192, 0.9505
    );

    return 100.0 * tmp*mat;
}

vec3 xyz2lab(vec3 c) {
    vec3 n = c / vec3(95.047, 100, 108.883);
    vec3 v;

    v.x = (n.x > 0.008856) ? pow(abs(n.x), 1.0 / 3.0) : (7.787 * n.x) + (16.0 / 116.0);
    v.y = (n.y > 0.008856) ? pow(abs(n.y), 1.0 / 3.0) : (7.787 * n.y) + (16.0 / 116.0);
    v.z = (n.z > 0.008856) ? pow(abs(n.z), 1.0 / 3.0) : (7.787 * n.z) + (16.0 / 116.0);

    return vec3((116.0 * v.y) - 16.0, 500.0 * (v.x - v.y), 200.0 * (v.y - v.z));
}
vec3 rgb2lab(vec3 c) {
    vec3 lab = xyz2lab(rgb2xyz(c));
    return vec3(lab.x / 100.0f, 0.5 + 0.5 * (lab.y / 127.0), 0.5 + 0.5 * (lab.z / 127.0));
}

void main()
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;
    vec3 col = rgb2lab(texture(iChannel0, uv).rgb);
    fragColor = vec4(col, .0);
}
