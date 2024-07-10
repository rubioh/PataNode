#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform float width;
uniform float radius;
uniform float height;
uniform float iTime;

#define time iTime*.1
#define pi 3.14159
#define tau 6.283

vec2 hash2( vec2 p ) 
{
    const vec2 k = vec2( 0.3183099, 0.3678794 );
    float n = 111.0*p.x + 113.0*p.y;
    return fract(n*fract(k*n));
}
float noise(in vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    float a = hash2(i).x;
    float b = hash2(i + vec2(1.0, 0.0)).x;
    float c = hash2(i + vec2(0.0, 1.0)).x;
    float d = hash2(i + vec2(1.0, 1.0)).x;
    vec2 u = f*f*(3.0-2.0*f);
    return mix(a, b, u.x) +
            (c - a)* u.y * (1.0 - u.x) +
            (d - b) * u.x * u.y;
}

mat2 makem2(in float theta){float c = cos(theta);float s = sin(theta);return mat2(c,-s,s,c);}

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

float fbm(in vec2 p)
{	
	float z=2.;
	float rz = 0.;
	vec2 bp = p;
	for (float i= 1.;i < 6.;i++)
	{
		rz+= abs((noise(p)-0.5)*2.)/z;
		z = z*2.;
		p = p*2.;
	}
	return rz;
}

float dualfbm(in vec2 p)
{
    //get two rotated fbm calls and displace the domain
	vec2 p2 = p*.7;
    float t = time;
	vec2 basis = vec2(fbm(p2-t*1.6),fbm(p2+t*1.7));
	basis = (basis-.5)*.2;
	p += basis;
	
	//coloring
	return fbm(p*makem2(time*0.2));
}
float circ(vec2 p) 
{
	float r = length(p);
	r = log(sqrt(r));
	return abs(mod(r*4.,tau)-3.14)*3.+.2;

}

void main()
{
    vec2 R = iResolution.xy;
    vec2 uv = (gl_FragCoord.xy*2.-R)/R.y;

    uv.y += height;
    float arc = arch(uv);
    float tmparc = arc;
    arc = smoothstep(0.01, 0., arc)*smoothstep(1.25, .3, -arc);

    
    vec2 p = uv;
    float L = arc;
    p *= 4.;

    float rz = dualfbm(p*min(-tmparc, .5));
    float artifacts_radious_fade = pow(max(1., 6.5*L), 0.2) ;
    rz = artifacts_radious_fade*rz + (1.-artifacts_radious_fade)*dualfbm(p+5.0*sin(time)); // Add flaoting things around portal
    float my_time = time + 0.08*rz;
    
	//rings
	p /= exp(mod((my_time*10. + rz),3.38159)); // offset from PI to make the ripple effect at the start  
	rz *= pow(abs((0.1-circ(p))), .9)*tmparc;
	
	//final color
	vec3 col = 0.4*vec3(.2 ,0.1,0.4)/rz;
	col=pow(abs(col),vec3(.99));
    col = col.yzx;
    col = pow(col*.33, vec3(1.5));

    vec4 color = vec4(col, 1.);


    fragColor = arc*color;
}
