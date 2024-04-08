#version 330 core

in vec4 in_vert;
in vec3 in_col;
out vec3 color;
out vec2 pos;

uniform sampler2D iChannel0;
uniform float N;
uniform float part_radius;

float hash(float x){
    return fract(sin(x*174.5783+.742)*1273.489);   
}

vec3 get_col(vec2 p, sampler2D sampler){
    vec2 uv = (p+1)/2;
    vec3 col = in_col;
    return col;
}

void main() {
    //color = vec3(1., gl_VertexID/N, 0.);
    color = get_col(in_vert.xy, iChannel0)+.05;
    //color = in_col;
    pos = in_vert.xy;
    //gl_PointSize = (hash(gl_VertexID)*part_radius-part_radius/2)*.00001 + part_radius;
    //gl_PointSize = part_radius;
    gl_Position = vec4(in_vert.xy, 0.0, 1.0);
}
