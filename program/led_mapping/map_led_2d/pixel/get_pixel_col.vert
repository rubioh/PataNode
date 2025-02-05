#version 330
in vec2 in_pos;
uniform sampler2D iChannel0;
out vec4 out_col;

void main(){
    ivec2 pos = ivec2(in_pos);
    out_col = clamp(texelFetch(iChannel0, pos, 0), vec4(0.), vec4(1.));
}
