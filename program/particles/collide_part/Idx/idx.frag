#version 330 core

out vec4 f_color;
in float ID;
in vec2 pos;

void main()
{
    vec2 p = gl_PointCoord.xy;
    float s2 = 1.-step(.5, length(p-.5));
    if (s2 != 0)
        f_color = vec4(pos, 0, float(ID));
    else
        f_color = vec4(-10);
}
