#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform float width;
uniform float radius;
uniform float y_offset;
uniform float iTime;
uniform float x_offset;
uniform float nrj;

#define time iTime*.1
#define pi 3.14159
#define tau 6.283



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
/* discontinuous pseudorandom uniformly distributed in [-0.5, +0.5]^3 */
vec3 random3(vec3 c) {
    float j = 4096.0*sin(dot(c,vec3(17.0, 59.4, 15.0)));
    vec3 r;
    r.z = fract(512.0*j);
    j *= .125;
    r.x = fract(512.0*j);
    j *= .125;
    r.y = fract(512.0*j);
    return r-0.5;
}

/* skew constants for 3d simplex functions */
const float F3 =  0.3333333;
const float G3 =  0.1666667;

/* 3d simplex noise */
float simplex3d(vec3 p) {
     /* 1. find current tetrahedron T and it's four vertices */
     /* s, s+i1, s+i2, s+1.0 - absolute skewed (integer) coordinates of T vertices */
     /* x, x1, x2, x3 - unskewed coordinates of p relative to each of T vertices*/
     
     /* calculate s and x */
     vec3 s = floor(p + dot(p, vec3(F3)));
     vec3 x = p - s + dot(s, vec3(G3));
     
     /* calculate i1 and i2 */
     vec3 e = step(vec3(0.0), x - x.yzx);
     vec3 i1 = e*(1.0 - e.zxy);
     vec3 i2 = 1.0 - e.zxy*(1.0 - e);
        
     /* x1, x2, x3 */
     vec3 x1 = x - i1 + G3;
     vec3 x2 = x - i2 + 2.0*G3;
     vec3 x3 = x - 1.0 + 3.0*G3;
     
     /* 2. find four surflets and store them in d */
     vec4 w, d;
     
     /* calculate surflet weights */
     w.x = dot(x, x);
     w.y = dot(x1, x1);
     w.z = dot(x2, x2);
     w.w = dot(x3, x3);
     
     /* w fades from 0.6 at the center of the surflet to 0.0 at the margin */
     w = max(0.6 - w, 0.0);
     
     /* calculate surflet components */
     d.x = dot(random3(s), x);
     d.y = dot(random3(s + i1), x1);
     d.z = dot(random3(s + i2), x2);
     d.w = dot(random3(s + 1.0), x3);
     
     /* multiply d by w^4 */
     w *= w;
     w *= w;
     d *= w;
     
     /* 3. return the sum of the four surflets */
     return dot(d, vec4(52.0));
}

float noise(vec3 m) {
    return   0.5333333*simplex3d(m)
            +0.2666667*simplex3d(2.0*m)
            +0.1333333*simplex3d(4.0*m)
            +0.0666667*simplex3d(8.0*m);
}

void main()
{
    vec2 R = iResolution.xy;
    vec2 uv = (gl_FragCoord.xy*2.-R)/R.y;

    uv.y += y_offset;
    uv.x += x_offset;

    float arc = arch(uv);
    float tmparc = arc;
    arc = smoothstep(0.01, 0., arc)*smoothstep(1.25, .3, -arc);

    vec2 p = gl_FragCoord.xy/iResolution.x;
    vec3 p3 = vec3(p, iTime*0.4);    

    float intensity = noise(vec3(p3*12.0+12.0))*(1.+nrj);
                          
    float t = clamp((uv.x * -uv.x * 0.16) + 0.15, 0., 1.);                         
    float y = abs(intensity * -t + uv.y);

    float g = pow(y, 0.2);
                          
    vec3 col = vec3(1.70, 1.48, 1.78);
    col = col * -g + col;                    
    col = col * col;
    col = col * col;

    float a = .6;
    uv.x = abs(uv.x);
    uv *= mat2(cos(a), sin(a), -sin(a), cos(a));

    t = clamp((uv.x * -uv.x * 0.16) + 0.15, 0., 1.);                         
    y = abs(intensity * -t + uv.y);

    g = pow(y, 0.2);
                          
    vec3 col2 = vec3(1.70, 1.48, 1.78);
    col2 = col2 * -g + col2;                    
    col2 = col2 * col2;
    col2 = col2 * col2;

    col += col2;
    a = 1.2;
    uv = (gl_FragCoord.xy*2.-R)/R.y;
    uv.y += y_offset;
    uv.x += x_offset;

    uv.x = abs(uv.x);
    uv *= mat2(cos(a), sin(a), -sin(a), cos(a));

    t = clamp((uv.x * -uv.x * 0.16) + 0.15, 0., 1.);                         
    y = abs(intensity * -t + uv.y);

    g = pow(y, 0.2);
                          
    col2 = vec3(1.70, 1.48, 1.78);
    col2 = col2 * -g + col2;                    
    col2 = col2 * col2;
    col2 = col2 * col2;

    col += col2;


    vec4 color = vec4(col, 1.);


    fragColor = arc*color;
}
