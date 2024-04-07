#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform float iTime;
uniform sampler2D iChannel0;

vec2 hash( vec2 p )
{
    //p = mod(p, 4.0); // tile
    p = vec2(dot(p,vec2(175.1,311.7)),
             dot(p,vec2(260.5,752.3)));
    return fract(sin(p+455.)*18.5453);
}

vec3 hash13(float p){
    vec3 x = vec3(p*17.256, mod(p, 32.659)*14.456, mod(p, 135.235)*17.235);
    return fract(sin(x)*vec3(8.5453, 11.2378, 11.5678));
}

vec2 hash2( vec2 p ) 
{
    const vec2 k = vec2( 0.3183099, 0.3678794 );
    float n = 111.0*p.x + 113.0*p.y;
    return fract(n*fract(k*n));
}

float len(vec2 uv){
    float N = 1.5+.5*cos(iTime/32.);
    return pow(pow(abs(uv.x), N) +  pow(abs(uv.y), N), 1./N);
}

float truchet(vec2 coord){
    float l = smoothstep(.45, .55, abs(len(coord)));
    l *= smoothstep(.45, .55, abs(len(coord-1.)));
    return l;
}

float truchet_border(vec2 coord, float width){
    float l = step(0.,  abs(len(coord)-.5) - width);
    l *= step(0., abs(len(coord-1.)-.5) - width);
    return l;
}

float flip(vec2 v, float w)
{
    v = fract(v/2.)-.5;
    return mix(w, 1. - w, step(0., v.x * v.y));
}

float pattern_in(vec2 v)
{
    vec2 id = floor(v);
    vec2 coord = fract(v);
    return 
        flip(v, hash(id).x < .5 ? 1.-truchet(coord) : truchet(vec2(1.-coord.x,coord.y)));
}

vec4 pattern_border(vec2 v, float width)
{
    vec2 id = floor(v);
    vec2 coord = fract(v);
    
    vec4 connex = texelFetch(iChannel0, ivec2(id), 0);

    float touch = connex.z < .5 ? truchet_border(coord, width) : truchet_border(vec2(1.-coord.x,coord.y), width);

    vec3 col = (1.-touch)*vec3(1.);
    if (connex.z> .5){
        if (coord.x<coord.y)
            col *= hash13(connex.y);
        else 
            col *= hash13(connex.x);
    }
    if (connex.z<.5){
        if (1.-coord.y<coord.x)
            col *= hash13(connex.y);
        else 
            col *= hash13(connex.x);
    }
    
    return vec4(connex.x, connex.y, connex.z, touch);
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.x;
    uv *= 15.;

    vec4 col = pattern_border(uv, .1);
    fragColor = vec4(col);
 }
