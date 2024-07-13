#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform float width;
uniform float radius;
uniform float y_offset;
uniform float x_offset;
uniform float iTime;

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

float saturate (in float f)
{
    return clamp(f,0.0,1.0);
}



void main()
{
    vec2 R = iResolution.xy;
    vec2 uv = (gl_FragCoord.xy*2.-R)/R.y;

    uv.y += y_offset;
    uv.x += x_offset;
    float arc = arch(uv);
    arc = smoothstep(0.01, 0., arc)*smoothstep(1.25, .3, -arc);

    
    float armRot = 1.6;
    float armCount = 10.;
    float time = iTime*.2;
    float pi = 3.14159;
    float tao = 2.*pi;
    vec4 innerColor = vec4(2.0,0.5,0.1,1.0);
    vec4 outerColor = vec4(0.8,0.6,1.0,1.0);
    vec4 white = vec4(1.);
    float orig_width = .3;
    float orig_radius = .7;
    float ra = orig_radius*radius;
    float rb = orig_width*width;
    vec2 p = uv;

    
    float d = length(p)-ra+rb;
    d *= .2;
    //d *= .4;

    //build arm rotation matrix
    float cosr = cos(armRot*sin(armRot*time));
    float sinr = sin(armRot*cos(armRot*time));
    mat2 rm = mat2 (cosr,sinr,-sinr,cosr);

    //calc arm rotation based on distance
    p = mix(p,p * rm,d);

        //find angle to middle
    float angle = (atan(p.y,p.x)/tao) * 0.5 + 0.5;
    //add the crinkle
    angle += sin(-time*5.0+fract(d*d*d)*800.0)*0.004;
    //calc angle in terms of arm number
    angle *= 2.0 * armCount;
    angle = fract(angle);
    //build arms & wrap the angle around 0.0 & 1.0
    float arms = abs(angle*2.0-1.0);
    //sharpen arms
    arms = pow(arms, 100.0*pow(arc, 8.) + 4.0)*3.;
    //calc radial falloff
    float bulk = 1.;
    //create glowy center
    vec4 color = mix(innerColor,outerColor,d*2.0);

    color = bulk * arms * color + bulk*0.1*mix(color,white,0.5)*pow(arc, 8.);


    fragColor = arc*color;
}
