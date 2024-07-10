#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform float width;
uniform float radius;
uniform float height;

float opSmoothUnion( float d1, float d2, float k )
{
    float h = clamp( 0.5 + 0.5*(d2-d1)/k, 0.0, 1.0 );
    return mix( d2, d1, h ) - k*h*(1.0-h);
}

float sdArc( in vec2 p, in vec2 sc, in float ra, float rb )
{
    // sc is the sin/cos of the arc's aperture
    p.x = abs(p.x);
    return ((sc.y*p.x>sc.x*p.y) ? length(p-sc*ra) :
                                  abs(length(p)-ra)) - rb;
}

float sdBox( in vec2 p, in vec2 b )
{
    vec2 d = abs(p)-b;
    return length(max(d,0.0)) + min(max(d.x,d.y),0.0);
}

vec3 arch(vec2 uv){
    float orig_width = .3;
    float orig_radius = .7;

    float angle = 3.14159;
    vec2 dir = vec2(0.);
    vec2 sc = vec2(cos(angle), sin(angle));
    float ra = orig_radius*radius;
    float rb = orig_width*width;

    float d = sdArc(-uv, sc, ra, rb);
    float alpha = atan(uv.x, uv.y);
    dir = vec2(sin(alpha), cos(alpha));
    
    float height_rec = .5;
    if (uv.y<0.){
        vec2 p = vec2(abs(uv.x), uv.y+.5)-vec2(radius*orig_radius, 0.);
        vec2 b = vec2(orig_width*width, height_rec);
        d = sdBox(p, b);
        dir = vec2(sign(uv.x), 0.);
    }
    
    return vec3(d, -dir);
}

vec2 getDir(vec2 uv){
    vec2 eps = vec2(1., 0.)*.000001;
    vec3 infos = arch(uv);
    return infos.yz;
}


void main()
{
    vec2 R = iResolution.xy;
    vec2 uv = (gl_FragCoord.xy*2.-R)/R.y;
    uv.y += height;
    float arc = arch(uv).x;
    vec2 dir = getDir(uv);

    arc = step(arc, 0.);
    vec3 col = arc *   vec3(dir, 0.)*(cos(iTime*.1)*.0000001+1.);
    fragColor = vec4(col*.001+vec3(dir, 0.), 1.);
}
