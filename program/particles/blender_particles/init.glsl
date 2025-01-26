#version 450 core

layout (local_size_x = 256) in;

layout (std430, binding = 0) buffer OutputBuffer1 {
    vec4 in_position[];
};

layout (std430, binding = 1) buffer OutputBuffer2 {
    vec4 in_velocity[];
};

layout (std430, binding = 2) buffer OutputBuffer3 {
    vec4 out_position[];
};

layout (std430, binding = 3) buffer OutputBuffer4 {
    vec4 out_velocity[];
};

void main() {
    uint index = gl_GlobalInvocationID.x;
    if (index >= 10000)
        return;
    in_position[index] = vec4(0., 0., 0., 0.);
    in_velocity[index] = vec4(0., 0., 0., 0.);
    out_position[index] = vec4(0., 0., 0., 0.);
    out_velocity[index] = vec4(0., 0., 0., 0.);
}
