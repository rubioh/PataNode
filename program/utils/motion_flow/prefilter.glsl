#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D iChannel0;

float luma(vec3 c){
    return dot(c, vec3(0.299, 0.587, 0.114));
}

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution;
    vec2 px = 1./iResolution;

    // 3x3 tent in compute-pixel units. The low pass matters: Lucas-Kanade on raw
    // camera luma measures sensor noise instead of movement.
    float acc = 0.;
    float wsum = 0.;

    for (int j = -1; j <= 1; j++){
        for (int i = -1; i <= 1; i++){
            float w = (i == 0 ? 2. : 1.) * (j == 0 ? 2. : 1.);
            acc += w * luma(texture(iChannel0, uv + vec2(i, j)*px).rgb);
            wsum += w;
        }
    }

    fragColor = vec4(acc/wsum, 0., 0., 1.);
}
