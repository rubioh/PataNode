#version 330 core
layout (location = 0) in vec2 in_position;
layout (location = 1) in vec2 in_tcs;

out vec2 p;
out vec2 tcs;

void main(){
	p = (in_position - .5) * 2.;
	p.y = -p.y;
	tcs = in_tcs;
    gl_Position = vec4(p, 0., 1.);
}