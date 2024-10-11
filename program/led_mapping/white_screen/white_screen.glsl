#version 330 core
layout (location=0) out vec4 fragColor;

void main()
{
    vec3 col = vec3(.9);
    fragColor = vec4(col,1.0);
}

