#version 330 core
layout (location=0) out vec4 fragColor;

uniform float on_tempo;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float nrj_low;
uniform float n_col;
uniform float go_x_phase;
uniform float x_phase_amp;
#define R iResolution


vec4 getCells(vec2 uv){

    float id_x = floor(uv.x*n_col);
    float coord_x = fract(uv.x*n_col);
    vec2 uvs = vec2(id_x/n_col, uv.y);

    vec4 col = texture(iChannel0, uvs);
    vec4 col2 = texture(iChannel0, uv);
    col = col*.97 + .03 + on_tempo*.0001;

    //float go_x = dot(col.rgb, vec3(.599, .127, .287));
    float go_x = cos(uv.y*20. + 2.*3.14159*uvs.x*x_phase_amp + go_x_phase)*.5 + .5;
    coord_x = coord_x - .5;
    
    float amp = (.25 + pow(nrj_low, .5)*2.);
    col *= 1.-smoothstep(0., .1, abs(coord_x)-go_x*.5*amp);
    
    //col = mix(col, col2, smoothstep(.0, .05, length(coord_x)-go_x*.5*amp));

    //col = col*

    return col;
}



void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/R;


   
    vec4 col = getCells(uv);


    fragColor = col;

}
