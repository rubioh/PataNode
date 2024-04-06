#version 330 core
layout (location=0) out vec4 fragColor;

uniform sampler2D iChannel0;
#define R iResolution

#define fetch(uv) texelFetch(iChannel0, uv, 0).xyz

float T(ivec2 uv){
    vec3 tolum = vec3(.299, .587, .114);
    vec3 data = fetch(uv);
    return dot(data, tolum);
}

vec3 getGradient(ivec2 uv){
    float sp0p1 = T(uv + ivec2(0,1));
    float sp0p0 = T(uv + ivec2(0,0));
    float sp0m1 = T(uv + ivec2(0,-1));

    float sp1p1 = T(uv + ivec2(1,1));
    float sp1p0 = T(uv + ivec2(1,0));
    float sp1m1 = T(uv + ivec2(1,-1));

    float sm1p1 = T(uv + ivec2(-1,1));
    float sm1p0 = T(uv + ivec2(-1,0));
    float sm1m1 = T(uv + ivec2(-1,-1));

    float Gx = -sm1p1 - 2.*sm1p0  - sm1m1 + sp1p1 + 2.*sp1p0 + sp1m1;
    float Gy = -sm1p1 - 2.*sp0p1  - sp1p1 + sm1m1 + 2.*sp0m1 + sp1m1;
    
    return vec3(Gx, -Gy, sqrt(Gx*Gx + Gy*Gy));
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    ivec2 uv = ivec2(gl_FragCoord.xy);
        
    vec3 gradient = getGradient(uv);

    fragColor = vec4(gradient,1.0);

}
