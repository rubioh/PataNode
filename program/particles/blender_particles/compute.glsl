#version 450 core

layout (local_size_x = 256) in;

layout (std430, binding = 0) buffer InputBuffer {
    vec4 in_position[];
};

layout (std430, binding = 1) buffer InputBuffer2 {
    vec4 in_velocity[];
};

layout (std430, binding = 2) buffer OutputBuffer {
    vec4 out_position[];
};

layout (std430, binding = 3) buffer OutputBuffer2 {
    vec4 out_velocity[];
};

void main() {
    uint index = gl_GlobalInvocationID.x;
    if (index >= 10000)
        return;
    vec4 velocity = in_velocity[index] + vec4(.01, 0., 0., 0.);
    vec4 position = in_position[index];

    out_position[index] = velocity + position;
}
