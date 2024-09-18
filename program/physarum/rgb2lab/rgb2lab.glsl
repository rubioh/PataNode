#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;

#define R iResolution
vec3 rgb2xyz(vec3 rgb) {
    // Normalize RGB values
    rgb = rgb / 255.0;

    // Apply gamma correction (sRGB to linear)
    rgb = mix(pow((rgb + 0.055) / 1.055, vec3(2.4)), rgb / 12.92, step(rgb, vec3(0.04045)));

    // Convert RGB to XYZ
    mat3 rgb2xyzMat = mat3(
        0.4124564, 0.3575761, 0.1804375,
        0.2126729, 0.7151522, 0.0721750,
        0.0193339, 0.1191920, 0.9503041
    );
    return rgb2xyzMat * rgb;
}

vec3 xyz2lab(vec3 xyz) {
    // Reference white (D65)
    vec3 white = vec3(0.95047, 1.00000, 1.08883);

    // Scale xyz by the reference white
    xyz = xyz / white;

    // Apply the nonlinear function
    xyz = mix(pow(xyz, vec3(1.0 / 3.0)), (xyz * 7.787) + (16.0 / 116.0), step(xyz, vec3(0.008856)));

    // Convert XYZ to LAB
    float L = (116.0 * xyz.y) - 16.0;
    float a = 500.0 * (xyz.x - xyz.y);
    float b = 200.0 * (xyz.y - xyz.z);

    return vec3(L, a, b);
}

vec3 rgb2lab(vec3 rgb) {
    vec3 xyz = rgb2xyz(rgb);
    vec3 lab = xyz2lab(xyz);
    return lab;
}

void main()
{
    vec2 uv = gl_FragCoord.xy/R;
    vec4 id = texture(iChannel0, uv).rgba;
    id.rgb = rgb2lab(id.rgb);
    fragColor = vec4(id.xxxx);
}
