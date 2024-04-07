#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform float iTime;
uniform float iFrame;
uniform sampler2D TruchetSampler;

vec2 hash( vec2 p )
{
    //p = mod(p, 4.0); // tile
    p = vec2(dot(p,vec2(175.1,311.7)),
             dot(p,vec2(260.5,752.3)));
    return fract(sin(p+455.)*18.5453);
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
    float l = smoothstep(0., .1, abs(len(coord)-.5) - width);
    l *= smoothstep(0., .1, abs(len(coord-1.)-.5) - width);
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

float pattern_border(vec2 v, float width, inout vec2 ID1, inout vec2 ID2)
{
    vec2 id = floor(v);
    ID1 = id;
    ID2 = id;
    vec2 coord = fract(v);
    float touch = hash(id).x < .5 ? truchet_border(coord, width) : truchet_border(vec2(1.-coord.x,coord.y), width);
    return touch;
}

vec2 transform(vec2 uv){
    return (uv-.5) * 1.;
}
#define T(U) texelFetch(TruchetSampler, ivec2(U), 0 )
#define left(T)    T.x
#define right(T)   T.y
#define bot(T)   ( T.z<1. ? T.x : T.y )
#define top(T)   ( T.z<1. ? T.y : T.x )
#define R iResolution.xy


void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;
    //uv -= .5;
    //uv = floor(uv*iResolution.xy);
    vec2 st = transform(uv);
    //if (iFrame == 0.){
    //    float truchet = (1.-pattern_border((uv-.5)*10., .1));
    //}
    //
    if (iFrame < 40){
        vec2 ID1 = vec2(0.);
        vec2 ID2 = vec2(0.);
        float truchet = (1.-pattern_border(gl_FragCoord.xy, .1, ID1, ID2));
        fragColor = vec4(1.+ ID1.x + ID1.y * 100., 
                         -(1.+ ID2.x + ID2.y * 100.), 
                         step(.5, hash(gl_FragCoord.xy).x), 
                         truchet);
        return;
    }
    else{
        uv *= R;
        vec4 self = texelFetch(TruchetSampler, ivec2(uv), 0);
        vec4 u = T(uv + vec2(0.,1.)); // up
        vec4 d = T(uv - vec2(0.,1.)); // down
        vec4 r = T(uv + vec2(1.,0.)); // right
        vec4 l = T(uv - vec2(1.,0.)); // left
        if (self.z == 1.){
            fragColor.x = min(self.x, 
                    min( (r.z == 1.) ? r.y : r.x, (d.z == 1.) ? d.y : d.y)); 
            fragColor.y = min(self.y,
                    min( (u.z == 1.) ? u.x : u.x, (l.z == 1.) ? l.x : l.y));

        }
        else{
            fragColor.x = min(self.x, 
                    min( (d.z == 1.) ? d.y : d.y, (l.z == 1.) ? l.x : l.y)); 
            fragColor.y = min(self.y,
                    min( (u.z == 1.) ? u.x : u.x, (r.z == 1.) ? r.y : r.x));
        }
        fragColor.zw = self.zw;
    }

 }
