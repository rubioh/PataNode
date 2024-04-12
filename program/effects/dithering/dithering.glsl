#version 430 core
layout (location=0) out vec4 fragColor;

uniform sampler2D iChannel0;

const float dither0[8] = float[](0., 32., 8., 40., 2., 34., 10., 42.);
const float dither1[8] = float[](48., 16., 56., 24., 50., 18., 58., 26.);
const float dither2[8] = float[](12., 44., 4., 36., 14., 46., 6., 38.);
const float dither3[8] = float[](60., 28., 52., 20., 62., 30., 54., 22.);
const float dither4[8] = float[](3., 35., 11., 43., 1., 33., 9., 41.);
const float dither5[8] = float[](51., 19., 59., 27., 49., 17., 57., 25.);
const float dither6[8] = float[](15., 47., 7., 39., 13., 45., 5., 37.);
const float dither7[8] = float[](63., 31., 55., 23., 61., 29., 53., 21);


const mat4 dither44 = 1/16.* mat4(0., 8., 2., 10., 12., 4., 14., 6., 3., 11., 1., 9., 15., 7., 13., 5.);


vec4 dither(ivec2 uv){
    
    int x = int(mod(float(uv.x), 4));
    int y = int(mod(float(uv.y), 4));
    /*
    float bayer;
    if (x == 0) bayer = dither0[y]*1./64.;
    else if (x == 1) bayer = dither1[y]*1./64.;
    else if (x == 2) bayer = dither2[y]*1./64.;
    else if (x == 3) bayer = dither3[y]*1./64.;
    else if (x == 4) bayer = dither4[y]*1./64.;
    else if (x == 5) bayer = dither5[y]*1./64.;
    else if (x == 6) bayer = dither6[y]*1./64.;
    else if (x == 7) bayer = dither7[y]*1./64.;
    */

    float bayer = dither44[x][y];

    vec4 col = texelFetch(iChannel0, uv, 0);
    
    col = floor((col + bayer)*2.)/2.-.5;
    col = clamp(col, vec4(0.), vec4(1.));

    return col;
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    ivec2 uv = ivec2(gl_FragCoord.xy);

    vec4 col = vec4(dither(uv));

    fragColor = col;
}
