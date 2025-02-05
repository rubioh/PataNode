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

uniform float damping_factor;
uniform float bounce_factor;
bool is_inside_aabb(vec3 position, vec3 aabb_location, vec3 aabb_size) {
    position.xyz -= aabb_location;
    return all(lessThan(position.xyz, aabb_size)) && all(greaterThan(position.xyz, vec3(0.)));
}

bool check_aabb_colision(vec3 position, vec3 future_position, vec3 aabb_location, vec3 aabb_size, out vec3 normal) {
    vec3 n = abs(future_position);
    if (n.x > n.y && n.x > n.z) {
        normal = vec3(1., 0, 0.);
    }
    else if (n.y > n.x && n.y > n.z) {
        normal = vec3(0., 1, 0.);
    } else {
        normal = vec3(0., 0, 1.);
    }
    normal *= sign(future_position);
    return is_inside_aabb(position, aabb_location, aabb_size) != is_inside_aabb(future_position, aabb_location, aabb_size);
}

void main() {
    uint index = gl_GlobalInvocationID.x;

    if (index >= 1000000)
        return;

    vec3 grativy = vec3(.0, -.0001, 0.);
    vec3 velocity = in_velocity[index].xyz + grativy - in_velocity[index].xyz * damping_factor;
    vec3 position = in_position[index].xyz;
    vec3 normal;
    if (check_aabb_colision(position, position + velocity, vec3(-5., -0.5, -2.5), vec3(10., 1., 5.), normal )) {
        velocity = reflect(in_velocity[index].xyz * bounce_factor, normal);
    }
    out_velocity[index].xyz = velocity;
    out_position[index].xyz = velocity + position;
}
