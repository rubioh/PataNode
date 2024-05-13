layout (location = 0) in vec3 in_position;
layout (location = 1) in vec3 in_normal;
layout (location = 2) in vec2 in_tc;
layout (location = 3) in vec3 in_color;

uniform mat4 model_transform;
uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

out vec2 tcs;
out vec3 normal;
out vec3 p;
out vec3 col;

void main() {
    vec4 v = vec4(in_position, 1.);
    mat4 mvp = model_transform * model *  view * projection;
    v = v * mvp;
    gl_Position = v;
	p = v.xyz;
    col = in_color;
    normal = (vec4(in_normal, 0.) * mvp).xyz;
    tcs = in_tc;
}
