#version 330 core

out vec4 f_color;
in vec3 color;
in vec2 pos;


//uniform sampler2D image;
//uniform vec2 iResolution;
//uniform float part_size;

void main()
{
    vec2 p = gl_PointCoord.xy;

    float dist = smoothstep(.5, .44, length(p - .5));
    float l = length(p-.5);
    float sigma = .1;
    //dist = exp(-pow(l, 2.)/sigma);
    //float d2 = smoothstep(.5, .44, length(p-.5));
    // Normalized pixel coordinates (from 0 to 1)
    vec3 col = color;
    //col = clamp(texture(image, uv).rgb, vec3(0.), vec3(1.));
    /*
    if (length(color)<.5){
        f_color = vec4(0.);
        return;
    }
    */
   //col = vec3(.9,0.3,0.4)/4;
    f_color = vec4(col, dist);
}
