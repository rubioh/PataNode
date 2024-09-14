#version 330 core

out vec4 f_color;
in vec2 pos;
in float sensor;

void main(){
    vec2 p = gl_PointCoord.xy;

    float dist = smoothstep(.5, .49, length(p - .5));
    f_color = vec4(.1*dist);
}
