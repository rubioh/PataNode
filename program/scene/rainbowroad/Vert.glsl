layout (location = 0) in vec2 in_position;

out vec2 p;

void main(){
	p = in_position;
    gl_Position = vec4(p, 0., 1.);
}
