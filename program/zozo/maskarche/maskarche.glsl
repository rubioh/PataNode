#version 330 core
layout (location=0) out vec4 fragColor;

uniform sampler2D iChannel0;
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

float arch(vec2 uv){
    float orig_width = .3;
    float orig_radius = .7;

    float angle = 3.14159;
    vec2 sc = vec2(cos(angle), sin(angle));
    float ra = orig_radius*radius;
    float rb = orig_width*width;
    float height_rec = .5;

    float d = length(uv)-ra+rb;

    vec2 p = uv + vec2(0., .5);
    vec2 b = vec2(ra-rb, height_rec);
    d = min(d, sdBox(p, b));

    d *= -1;
    return d;
}


void main()
{
    vec2 R = iResolution.xy;
    vec2 uv = (gl_FragCoord.xy*2.-R)/R.y;


    vec4 tex = texture(iChannel0, gl_FragCoord.xy/R.xy);

    uv.y += height;
    float arc = arch(uv);
    arc = smoothstep(0.01, 0., arc)*smoothstep(1.25, .3, -arc);
    fragColor = tex*arc;
}
