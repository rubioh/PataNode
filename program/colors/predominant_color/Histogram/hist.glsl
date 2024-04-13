#version 330

uniform sampler2D iChannel0;
uniform float pass_number;
uniform vec3 to_skip[3];
uniform int to_skip_size;

out vec4 fragColor;

vec4 white_to_black(vec4 col){
    float thresh_white = .4;
    float sum = .0;
    vec4 colc = col;
    colc.rgb = clamp(colc.rgb, vec3(0.), vec3(1.));
    sum += abs(colc.r-colc.g);
    sum += abs(colc.r-colc.b);
    sum += abs(colc.b-colc.g);
    if (sum < thresh_white) return vec4(vec3(0.), 1.);
    else return colc;
}

bool coldiff(vec3 col1, vec3 col2) {
    float threshold = .5;
    col1 = normalize(col1);
    col2 = normalize(col2);
    vec3 delta = abs(col1 - col2);
    float sum = delta.x+delta.y+delta.z;
    return sum < threshold;
}

vec4 colors_to_skip_to_black(vec4 col) {
    for (int i = 0; i < to_skip_size; ++i) {

        if (coldiff(col.xyz, to_skip[i].xyz)) {
            col = vec4(vec3(.0), 0.);
        }
    }
    return col;
}

vec4 getCol(ivec2 uv){

    uv *= 2;

    if (pass_number == 0) uv *= 4;

    vec4 col00 = texelFetch(iChannel0, uv, 0);
    vec4 col10 = texelFetch(iChannel0, uv+ivec2(1,0), 0);
    vec4 col01 = texelFetch(iChannel0, uv+ivec2(0,1), 0);
    vec4 col11 = texelFetch(iChannel0, uv+ivec2(1,1), 0);

    if (pass_number == 0){
        col00 = white_to_black(col00);
        col10 = white_to_black(col10);
        col01 = white_to_black(col01);
        col11 = white_to_black(col11);

        col00 = colors_to_skip_to_black(col00);
        col10 = colors_to_skip_to_black(col10);
        col01 = colors_to_skip_to_black(col01);
        col11 = colors_to_skip_to_black(col11);

    }

    vec4 res = vec4(0.);

    float b00 = 1.;
    float b10 = 1.;
    float b01 = 1.;
    float b11 = 1.;
    float lum_thresh = .2;
    if (length(col00.rgb)/sqrt(3)<lum_thresh){
        b00 = 0.;
    }
    if (length(col10.rgb)/sqrt(3)<lum_thresh){
        b10 = 0.;
    }
    if (length(col01.rgb)/sqrt(3)<lum_thresh){
        b01 = 0.;
    }
    if (length(col11.rgb)/sqrt(3)<lum_thresh){
        b11 = 0.;
    }

    float cnt_00 = col00.a*b00;
    float cnt_10 = col10.a*b10;
    float cnt_01 = col01.a*b01;
    float cnt_11 = col11.a*b11;

    float thresh = .5;
    if (b00 > .0){
        if (b10 > .0){
            if (length(col00 - col10) < thresh)
                cnt_00 += col10.a;
        }
        if (b01 > .0){
            if (length(col00 - col01) < thresh)
                cnt_00 += col01.a;
        }
        if (b11 > .0){
            if (length(col00 - col11) < thresh)
                cnt_00 += col11.a;
        }
    }
    if (b10 > .0){
        if (b01 > .0){
            if (length(col10 - col01) < thresh)
                cnt_10 += col10.a;
        }
        if (b11 > .0){
            if (length(col10 - col11) < thresh)
                cnt_10 += col11.a;
        }
    }
    if (b01 > .0){
        if (b11 > .0){
            if (length(col01 - col11) < thresh)
                cnt_01 += col11.a;
        }
    }

    if (cnt_00 >= cnt_01 && cnt_00 >= cnt_10){
        res.rgb = col00.rgb;
        res.a = cnt_00;
    }
    else{
        if (cnt_01 >= cnt_10){
            res.rgb = col01.rgb;
            res.a = cnt_01;
        }
        else{
            res.rgb = col10.rgb;
            res.a = cnt_10;
        }
    }
    return res;
}

void main()
{
    ivec2 uv = ivec2(gl_FragCoord.xy);
    vec4 col = getCol(uv);
    fragColor = col;
}
