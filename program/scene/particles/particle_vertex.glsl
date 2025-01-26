#version 330 core

layout (location = 0) in vec3 in_position;
uniform mat4 projection;

out vec3 p;
out vec3 col;

void main() {
    vec4 v = vec4(in_position, 1.);
    v = v * projection;
    gl_Position = v;
	p = v.xyz;
    col = vec3(1.);
}
