#version 330 core

in vec4 in_vert;
out vec2 pos;
out float ID;

void main() {
    //color = vec3(1., gl_VertexID/N, 0.);
    pos = in_vert.xy;
    ID = gl_VertexID;
    gl_Position = vec4(in_vert.xy, 0.0, 1.0);
}
