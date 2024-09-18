#version 330 core

in vec4 in_infos;
out vec2 pos;
out float sensor;

void main(){
    pos = in_infos.xy;
    sensor = in_infos.w;
    gl_Position = vec4(in_infos.xy, 0., 1.);
}
