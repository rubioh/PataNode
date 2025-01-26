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

bool is_inside_aabb(vec4 position, vec3 aabb_location, vec3 aabb_size) {
    position.xyz -= aabb_location;
    return all(lessThan(position.xyz, aabb_size)) && all(greaterThan(position.xyz, vec3(0.)));
}

bool check_aabb_colision(vec4 position, vec4 future_position, vec3 aabb_location, vec3 aabb_size) {
    return is_inside_aabb(position, aabb_location, aabb_size) != is_inside_aabb(future_position, aabb_location, aabb_size);
}

void main() {
    uint index = gl_GlobalInvocationID.x;

    if (index >= 1000000)
        return;

    float damping = 0.0001;
    float bounce_factor = .7;
    vec4 grativy = vec4(.0, -.0001, 0., 0.);
    vec4 velocity = in_velocity[index] + grativy - in_velocity[index] * damping;
    vec4 position = in_position[index];

    if (check_aabb_colision(position, position + velocity, vec3(-.1), vec3(.2))) {
        velocity = in_velocity[index] * -bounce_factor;
    }
    out_velocity[index] = velocity;
    out_position[index] = velocity + position;
}
