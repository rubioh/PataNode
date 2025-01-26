#version 450 core
#define M1 1597334677U     //1719413*929
#define M2 3812015801U     //140473*2467*11
#define M3 3299493293U     //467549*7057

#define F0 (1.0/float(0xffffffffU))

#define hash(n) n*(n^(n>>15))

#define coord1(p) (p*M1)
#define coord2(p) (p.x*M1^p.y*M2)
#define coord3(p) (p.x*M1^p.y*M2^p.z*M3)

float hash1(uint n){return float(hash(n))*F0;}
vec2 hash2(uint n){return vec2(hash(n)*uvec2(0x1U,0x3fffU))*F0;}
vec3 hash3(uint n){return vec3(hash(n)*uvec3(0x1U,0x1ffU,0x3ffffU))*F0;}
layout (local_size_x = 256) in;

uint lowbias32(uint x)
{
    x ^= x >> 16;
    x *= 0x7feb352dU;
    x ^= x >> 15;
    x *= 0x846ca68bU;
    x ^= x >> 16;
    return x;
}

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
    vec3 bias = (hash3(index) - vec3(.5)) * 0.01;

    if (index >= 1000000)
        return;
    in_position[index] = vec4(0., 0., 0., 0.);
    in_velocity[index] = vec4(bias.x, bias.y, bias.z,0.);
    out_position[index] = vec4(0., 0., 0., 0.);
    out_velocity[index] = vec4(bias.x, bias.y, bias.z, 0.);
}
