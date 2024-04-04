#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;

#define R iResolution
#define PI 3.1415


vec4 SST(vec2 uv){
    vec2 d = 1./R.xy;
    vec3 Gx =  (
           -1.0 * texture(iChannel0, uv + vec2(-d.x, -d.y)).xyz +
           -2.0 * texture(iChannel0, uv + vec2(-d.x,  0.0)).xyz +
           -1.0 * texture(iChannel0, uv + vec2(-d.x,  d.y)).xyz +
           +1.0 * texture(iChannel0, uv + vec2( d.x, -d.y)).xyz +
           +2.0 * texture(iChannel0, uv + vec2( d.x,  0.0)).xyz +
           +1.0 * texture(iChannel0, uv + vec2( d.x,  d.y)).xyz
           ) / 4.0;
    vec3 Gy = (
           -1.0 * texture(iChannel0, uv + vec2(-d.x, -d.y)).xyz +
           -2.0 * texture(iChannel0, uv + vec2( 0.0, -d.y)).xyz +
           -1.0 * texture(iChannel0, uv + vec2( d.x, -d.y)).xyz +
           +1.0 * texture(iChannel0, uv + vec2(-d.x,  d.y)).xyz +
           +2.0 * texture(iChannel0, uv + vec2( 0.0,  d.y)).xyz +
           +1.0 * texture(iChannel0, uv + vec2( d.x,  d.y)).xyz
           ) / 4.0;
    return vec4(dot(Gx, Gx), dot(Gy, Gy), dot(Gy, Gx), .0);
}

void main()
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;
    vec4 SST = SST(uv);
    fragColor = SST;
}
