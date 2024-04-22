#version 330 core
layout (location=0) out vec4 fragColor;

#define AA 1   // make this 2 or 3 for antialiasing
const float tmul = .1;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float stride;
uniform float beat_count;
uniform float low1;
uniform float low2;
uniform float drop;
uniform float animate;
uniform float shape;
uniform float on_chill;
uniform float ro;
float sdPlane( vec3 p )
{
    return p.y;
}

float sdSphere( vec3 p, float s )
{
    return length(p)-s;
}

float hash( float n )
{
    return fract(sin(n)*43758.5453);
}

float sdBox( vec3 p, vec3 b )
{
    vec3 d = abs(p) - b;
    return min(max(d.x,max(d.y,d.z)),0.0) + length(max(d,0.0));
}

float sdEllipsoid( in vec3 p, in vec3 r )
{
    float k0 = length(p/r);
    float k1 = length(p/(r*r));
    return k0*(k0-1.0)/k1;

}

float sdRoundBox( in vec3 p, in vec3 b, in float r )
{
    vec3 q = abs(p) - b;
    return min(max(q.x,max(q.y,q.z)),0.0) + length(max(q,0.0)) - r;
}

float sdTorus( vec3 p, vec2 t )
{
    return length( vec2(length(p.xz)-t.x,p.y) )-t.y;
}
vec3 pal( in float t, in vec3 a, in vec3 b, in vec3 c, in vec3 d )
{
    return a + b*cos( 6.28318*(c*t+d) );
}
float sdHexPrism( vec3 p, vec2 h )
{
    vec3 q = abs(p);

    const vec3 k = vec3(-0.8660254, 0.5, 0.57735);
    p = abs(p);
    p.xy -= 2.0*min(dot(k.xy, p.xy), 0.0)*k.xy;
    vec2 d = vec2(
       length(p.xy - vec2(clamp(p.x, -k.z*h.x, k.z*h.x), h.x))*sign(p.y - h.x),
       p.z-h.y );
    return min(max(d.x,d.y),0.0) + length(max(d,0.0));
}

float sdCapsule( vec3 p, vec3 a, vec3 b, float r )
{
    vec3 pa = p-a, ba = b-a;
    float h = clamp( dot(pa,ba)/dot(ba,ba), 0.0, 1.0 );
    return length( pa - ba*h ) - r;
}

float sdRoundCone( in vec3 p, in float r1, float r2, float h )
{
    vec2 q = vec2( length(p.xz), p.y );

    float b = (r1-r2)/h;
    float a = sqrt(1.0-b*b);
    float k = dot(q,vec2(-b,a));

    if( k < 0.0 ) return length(q) - r1;
    if( k > a*h ) return length(q-vec2(0.0,h)) - r2;

    return dot(q, vec2(a,b) ) - r1;
}

float dot2(in vec3 v ) {return dot(v,v);}
float sdRoundCone(vec3 p, vec3 a, vec3 b, float r1, float r2)
{
    // sampling independent computations (only depend on shape)
    vec3  ba = b - a;
    float l2 = dot(ba,ba);
    float rr = r1 - r2;
    float a2 = l2 - rr*rr;
    float il2 = 1.0/l2;

    // sampling dependant computations
    vec3 pa = p - a;
    float y = dot(pa,ba);
    float z = y - l2;
    float x2 = dot2( pa*l2 - ba*y );
    float y2 = y*y*l2;
    float z2 = z*z*l2;

    // single square root!
    float k = sign(rr)*rr*rr*x2;
    if( sign(z)*a2*z2 > k ) return  sqrt(x2 + z2)        *il2 - r2;
    if( sign(y)*a2*y2 < k ) return  sqrt(x2 + y2)        *il2 - r1;
                            return (sqrt(x2*a2*il2)+y*rr)*il2 - r1;
}

float sdEquilateralTriangle(  in vec2 p )
{
    const float k = 1.73205;//sqrt(3.0);
    p.x = abs(p.x) - 1.0;
    p.y = p.y + 1.0/k;
    if( p.x + k*p.y > 0.0 ) p = vec2( p.x - k*p.y, -k*p.x - p.y )/2.0;
    p.x += 2.0 - 2.0*clamp( (p.x+2.0)/2.0, 0.0, 1.0 );
    return -length(p)*sign(p.y);
}

float sdTriPrism( vec3 p, vec2 h )
{
    vec3 q = abs(p);
    float d1 = q.z-h.y;
    h.x *= 0.866025;
    float d2 = sdEquilateralTriangle(p.xy/h.x)*h.x;
    return length(max(vec2(d1,d2),0.0)) + min(max(d1,d2), 0.);
}

// vertical
float sdCylinder( vec3 p, vec2 h )
{
    vec2 d = abs(vec2(length(p.xz),p.y)) - h;
    return min(max(d.x,d.y),0.0) + length(max(d,0.0));
}

// arbitrary orientation
float sdCylinder(vec3 p, vec3 a, vec3 b, float r)
{
    vec3 pa = p - a;
    vec3 ba = b - a;
    float baba = dot(ba,ba);
    float paba = dot(pa,ba);

    float x = length(pa*baba-ba*paba) - r*baba;
    float y = abs(paba-baba*0.5)-baba*0.5;
    float x2 = x*x;
    float y2 = y*y*baba;
    float d = (max(x,y)<0.0)?-min(x2,y2):(((x>0.0)?x2:0.0)+((y>0.0)?y2:0.0));
    return sign(d)*sqrt(abs(d))/baba;
}

float sdCone( in vec3 p, in vec3 c )
{
    vec2 q = vec2( length(p.xz), p.y );
    float d1 = -q.y-c.z;
    float d2 = max( dot(q,c.xy), q.y);
    return length(max(vec2(d1,d2),0.0)) + min(max(d1,d2), 0.);
}

float dot2( in vec2 v ) { return dot(v,v); }
float sdCappedCone( in vec3 p, in float h, in float r1, in float r2 )
{
    vec2 q = vec2( length(p.xz), p.y );

    vec2 k1 = vec2(r2,h);
    vec2 k2 = vec2(r2-r1,2.0*h);
    vec2 ca = vec2(q.x-min(q.x,(q.y < 0.0)?r1:r2), abs(q.y)-h);
    vec2 cb = q - k1 + k2*clamp( dot(k1-q,k2)/dot2(k2), 0.0, 1.0 );
    float s = (cb.x < 0.0 && ca.y < 0.0) ? -1.0 : 1.0;
    return s*sqrt( min(dot2(ca),dot2(cb)) );
}

#if 0
// bound, not exact
float sdOctahedron(vec3 p, float s )
{
    p = abs(p);
    return (p.x + p.y + p.z - s)*0.57735027;
}
#else
// exacy distance
float sdOctahedron(vec3 p, float s)
{
    p = abs(p);

    float m = p.x + p.y + p.z - s;

    vec3 q;
         if( 3.0*p.x < m ) q = p.xyz;
    else if( 3.0*p.y < m ) q = p.yzx;
    else if( 3.0*p.z < m ) q = p.zxy;
    else return m*0.57735027;

    float k = clamp(0.5*(q.z-q.y+s),0.0,s);
    return length(vec3(q.x,q.y-s+k,q.z-k));
}
#endif


float length2( vec2 p )
{
    return sqrt( p.x*p.x + p.y*p.y );
}

float length6( vec2 p )
{
    p = p*p*p; p = p*p;
    return pow( p.x + p.y, 1.0/6.0 );
}

float length8( vec2 p )
{
    p = p*p; p = p*p; p = p*p;
    return pow( p.x + p.y, 1.0/8.0 );
}

float sdTorus82( vec3 p, vec2 t )
{
    vec2 q = vec2(length2(p.xz)-t.x,p.y);
    return length8(q)-t.y;
}

float sdTorus88( vec3 p, vec2 t )
{
    vec2 q = vec2(length8(p.xz)-t.x,p.y);
    return length8(q)-t.y;
}

float sdCylinder6( vec3 p, vec2 h )
{
    return max( length6(p.xz)-h.x, abs(p.y)-h.y );
}

//------------------------------------------------------------------
vec3 tex3D(sampler2D t, in vec3 p, in vec3 n ){

    n = max(abs(n), 0.001);
    n /= dot(n, vec3(1));
    vec3 tx = texture(t, p.yz).xyz;
    vec3 ty = texture(t, p.zx).xyz;
    vec3 tz = texture(t, p.xy).xyz;

    // Textures are stored in sRGB (I think), so you have to convert them to linear space
    // (squaring is a rough approximation) prior to working with them... or something like that. :)
    // Once the final color value is gamma corrected, you should see correct looking colors.
    return (tx*tx*n.x + ty*ty*n.y + tz*tz*n.z);
}

float opS( float d1, float d2 )
{
    return max(-d2,d1);
}

vec2 opU( vec2 d1, vec2 d2 )
{
    return (d1.x<d2.x) ? d1 : d2;
}

vec3 opRep( vec3 p, vec3 c )
{
    return mod(p,c)-0.5*c;
}

vec3 opTwist( vec3 p )
{
    float  c = cos(10.0*p.y+10.0);
    float  s = sin(10.0*p.y+10.0);
    mat2   m = mat2(c,-s,s,c);
    return vec3(m*p.xz,p.y);
}

vec3 getcol(float x1) {
    if (on_chill < .1) {
        vec3 col[3] = vec3[3] (vec3(0.120,0.737,0.737), vec3(0.920,0.137,0.137),
            vec3(0.720,.237,0.637));
        return col[int(mod(x1, 3.))] * low2;
    }
//return vec3(0.120,0.737,0.737);
//return vec3(.0, 1., .0);
//float x2= mod(iTime / 3., 7.) + 0.;
float x2 = 0.;
x1+= iTime * .053;
float x = fract(x1 / 1.);
//x2=0.;
    vec3 cols[7] = vec3[7] (pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.0,0.33,0.67) ),
    pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.0,0.10,0.20) ),
    pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.3,0.20,0.20) ),
    pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,0.5),vec3(0.8,0.90,0.30) ),
    pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,0.7,0.4),vec3(0.0,0.15,0.20) ),
    pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(2.0,1.0,0.0),vec3(0.5,0.20,0.25) ),
    pal( x, vec3(0.8,0.5,0.4),vec3(0.2,0.4,0.2),vec3(2.0,1.0,1.0),vec3(0.0,0.25,0.25) )
    );
    return mix( cols[int(x2)], cols[int(mod(x2, 7.)) + 1] , fract(x2));
}

//------------------------------------------------------------------
#define ANIMATE
#define ZERO (min(iFrame,0))

//------------------------------------------------------------------
mat2 rotate2d(float _angle){
    return mat2(cos(_angle),-sin(_angle),
                sin(_angle),cos(_angle));
}

float o2(){
return 0.;
#ifndef ANIMATE
return 0.;
#endif
    return .5 + sin(tmul * iTime / 12.) * .5;
}

float o(){
if (animate < .1)
    return shape;
//return 1.;
return .5 + sin(tmul * iTime) * .5;
}

vec3 kal(vec3 p) {
    if (ro > 1.6)
    p.xy *= rotate2d(iTime / 20.);
if (drop == 0.)
        return p;
p = abs(p);
p.xy*=rotate2d(iTime / 8.);
p=abs(p);p.xy*=rotate2d(tmul * iTime / 18.);
p=abs(p);
return p;
p.xy*=rotate2d(tmul*iTime / 1.);
    p.y = abs(p.y);
    p.x = abs(p.x);
    p.xy*=rotate2d(tmul*iTime / 2.);
        p.y = abs(p.y);
    p.x = abs(p.x);
    p.x-=.3;
    p.xy*=rotate2d(tmul*-iTime / 4.);
p.x-=.3;
    p.y = abs(p.y);
    p.x = abs(p.x);
    p.xy*=rotate2d(tmul*iTime / 6.);
//p.x-=.1;
    p.y -= .2;
    p.y+=.1;
    return p;
}
vec3 neon_col(float id) {
    return getcol(id);
    vec3 c =  .5*pal( id, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,0.5),vec3(0.8,0.90,0.30) );
    return normalize(c);
}

float mapPillars(in vec3 p) {
    float r = 15.;

    float r3 = 15.;
    float r2=.4;
    vec3 p2  = p;
    p2.z += 5.;
    float id = hash( floor(p.z/r) *r );
    p.xy *= rotate2d(tmul * iTime + id * 6.28);

    p.z = mod(p.z, r) - r / 2.;
    p2.z = mod(p2.z, r3) - r3 / 2.;

       float ds =  sdTorus(p2.xzy, vec2(.4, .05));

    p.x = mod(p.x, r2) - r2/2.;
    return min(length(p.xz) -.05, ds);
}

float mapBalls(in vec3 p, out vec3 lightCol) {
    //return 1e10;
    float r = .5;
    p.z += tmul * iTime * 6.;
    vec3 id = floor(p/r) *r;
    float h = hash( hash(id.x) + hash(id.y)+hash(id.z) );
    float s = .02;
    p = mod(p, r) - r/2.;
    lightCol = 2.*pal( hash(h), vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,0.5),vec3(0.8,0.90,0.30) );
    if (h < .9)
        return 1.;
    return length(p) - s;
}
float mapHexagonLight(in vec3 p, out vec3 lightCol) {
    float r = 5.;
    float t = p.z;

    lightCol = vec3(1., 0., 0.);
    float id = hash( floor( (p.z + -15.*iTime * tmul) / r) * r); // 5
    float a = 3.14 / 6.;
    p.z = mod(p.z,r)-r/2.;
    lightCol = neon_col(id * 12.);
  //  lightCol = neon_col(p.z / 5. + beat_count);
        float h = mix(.66, 1.05, o());
    float s = .02;

    vec2 sh = vec2(s, h);
    float d1 = sdCylinder(p, sh);
    p.xy *= rotate2d(a);

    float d2 = sdCylinder(p, sh);
    p.xy *= rotate2d(a);
    float d3 = sdCylinder(p, sh);
    p.xy *= rotate2d(a);
    float d4 = sdCylinder(p, sh);
    p.xy *= rotate2d(a);
    float d5 = sdCylinder(p, sh);
    p.xy *= rotate2d(a);
    float d6 = sdCylinder(p,sh);
    float u = min (min(d1, d3), min( min(d2, d6), min(d4, d5)) );

    return u;
}
float mapLight(in vec3 p, out vec3 lightCol) {
   // return mapHexagonLight(p,lightCol);
  float r = 5.;
  float t = p.z;
  lightCol = vec3(1., 0., 0.);
      float id = hash( floor( (p.z + beat_count) / r) * r); // 5
  //p.xy *= rotate2d(p.z + iTime + id);
//p.xy *= 5.5;
    lightCol = neon_col( floor(p.z / 5.) * 1. + beat_count);

    p.z = mod(p.z,r)-r/2.;
    //lightCol = neon_col(id * 12.);

//    return length(p) - .1;
    float a = mix(3.15, 2.6, o());

    float h = mix(.66, 1.05, o());
    float s = .02;
    float ox = mix(.65, .5, o());
    float of = .81;
    float of2 = 0.196;
    vec2 sh = vec2(s, h);
    float d1 = sdCylinder(p.yxz + vec3(-of, 0., 0.), sh);
    float d4 = sdCylinder(p.yxz + vec3(.45 + o() / 1., 0., 0.), sh * (1.-o()));
    vec3 p2 = p;
    p.xy *= rotate2d(a);
    float d2 = sdCylinder(p.xyz + vec3(-ox, of2, 0.), sh);
    p2.xy *= rotate2d(-a);
    float d3 = sdCylinder(p2.xyz + vec3(ox, of2, 0.), sh);

    float dt= min(min(d4, d2), min(d1, d3));
    return dt;
    float ds = sdTorus(p.xzy, vec2(.9, .01) );
    return min(ds, dt);
    return mix(dt, ds, sin(iTime * tmul) * .5 + .5);
   /*
        pos.y *= -1.;
    pos.y+=.2;
//    float a = 2.1;
    float a = mix(1.55, 2.1, o());

    float d4 = sdCylinder(pos * vec3(1., -1., 1.) + vec3(0., 0.6 * o(), 0.),vec2(.02, 1.9));
    float d1 = sdCylinder(pos,vec2(.02, 1.9));
    vec3 p2 = pos;
    pos.xy *= rotate2d(a);
    float d2 = sdCylinder(pos,vec2(.02, 1.9));
    p2.xy *= rotate2d(-a);
    float d3 = sdCylinder(p2,vec2(.02, 1.9));
    return min(d1, min(d2, min(d3, d4))) ;*/
}


vec3 get_light(in vec3 p, out float l, bool rm) {
    vec3 lc;
    float s;
    p = kal(p);
    s = mapLight(p, lc);
    l=s;
    if (rm) {
        pow(s, 3.);
        return lc * (.0002 / (.001 + s *s));
    }
    return lc * (.2 / (.001+s * s * s * s));
}

vec3 rmLight(in vec3 ro, vec3 rd, float d) {
    vec3 out_col = vec3(0.);
//return vec3(0.);
    float t = 0.;
    float oui = 0.;
    for (int i = 0; i < 80; ++i) {
        vec3 p = ro + rd * t;
        p = kal(p);
        //if (d<t)
        out_col += get_light(p,oui, true);
        vec3 lb;
        //float ii = mapBalls(p, lb);
       // out_col += lb * (.0005 / (.001 + ii*ii));
        t += .1;
    }
    return vec3(out_col);
}

float mapPlan(in vec3 pos, out float mat) {
    pos.y-=.3;
  //  pos.y += sin(pos.z * 2.) / 112.;
    float d1 = pos.y + 1.;
    vec3 p2 = pos;
    float r = .4;
    float h = .05;
    vec2 id = floor(pos.xz / r) * r;
    float ha = 0.;//hash(id.x + id.y);
    mat = ha < .7 ? 0. : 1.;
    p2.x = mod(pos.x, r) - r / 2.;
    float d2 = abs(p2.x);
    d2 = max(d2, abs(p2.y+1.) - h );

    vec3 p3 = pos;
    p3.z = mod(pos.z, r) - r / 2.;
    float d3 = abs(p3.z);
    d3 = max(d3, abs(p3.y+1.) - h );
    return min(d1,min(d2, d3));
}



float mapTrianglePlan(in vec3 pos, out float id) {
   // pos.xy *= rotate2d(iTime / 4.);
    pos.y *= -1.;
    pos.y+=.2;
  //  pos.z-=iTime * 2.;
//    float a = 2.1;
    float a = mix(1.55, 2.1, o());

    float d4 = mapPlan(pos * vec3(1., -1., 1.) + vec3(0., 0.8 * o(), 0.) , id);
    float d1 = mapPlan(pos, id);
    vec3 p2 = pos;
    pos.xy *= rotate2d(a);
    float d2 = mapPlan(pos, id);
    p2.xy *= rotate2d(-a);
    float d3 = mapPlan(p2, id);
    return min(d1, min(d2, min(d3, d4))) ;
}

float mapHexagon(in vec3 pos, out float id) {

    float a = 3.14 / 3.;
    float d1 = mapPlan(pos, id);
    pos.xy *= rotate2d(a);
    float d2 = mapPlan(pos, id);
    pos.xy *= rotate2d(a);
    float d3 = mapPlan(pos, id);
    pos.xy *= rotate2d(a);
    float d4 = mapPlan(pos, id);
    pos.xy *= rotate2d(a);
    float d5 = mapPlan(pos, id);
    pos.xy *= rotate2d(a);
    float d6 = mapPlan(pos, id);
    return min (min(d1, d3), min( min(d2, d6), min(d4, d5)) );
}

float mapTunnel(in vec3 pos, out float id) {
//    pos.xy *= rotate2d(pos.z + iTime);
//    pos.xy *= rotate2d( mod(iTime, 6.28) * 1. );
    float d1 =  mapHexagon(pos, id);
    float d2 = mapTrianglePlan(pos, id);
    return mix(d1, d2, smoothstep(-.1, .0, sin(pos.z / 12.)));
}
vec2 map( in vec3 pos, out vec3 lightCol, out float id)
{
    pos = kal(pos);
    vec2 res = vec2( 1e10, 0.0 );
    float d;

    if ( (d = mapTunnel(pos, id) ) < res.x ) {
        res.x = d;
        res.y = 1.;
    }

    vec3 clight;
    vec3 lightColtmp;
    if ( (d = mapLight(pos, clight) ) < res.x ) {
        res.x = d;
        res.y = 2.;
        lightCol = clight;
    }
    if ( (d = mapPillars(pos) ) < res.x ) {
        res.x = d;
        res.y = 1.;
    }
    return res;
}

const float maxHei = 0.8;

vec2 castRay( in vec3 ro, in vec3 rd, out vec3 lightCol, bool ref, out float mat)
{
    vec2 res = vec2(-1.0,-1.0);

    float tmin = 1.0;
    float tmax = 390.0;
    int num_step = ref ? 70 : 70;
    // raymarch primitives
    {

        float t = tmin;
        for( int i=0; i<num_step && t<tmax; i++ )
        {
            vec2 h = map( ro+rd*t , lightCol, mat);
            if( abs(h.x)<(0.0001*t) )
            {
                res = vec2(t,h.y);
                 break;
            }
            t += h.x;
        }
    }

    return res;
}



// https://iquilezles.org/articles/normalsSDF
vec3 calcNormal( in vec3 pos )
{
    vec3 a;
    float b;
    vec2 e = vec2(1.0,-1.0)*0.5773*0.0005;
    return normalize( e.xyy*map( pos + e.xyy,a,b ).x +
					  e.yyx*map( pos + e.yyx ,a,b).x +
					  e.yxy*map( pos + e.yxy ,a ,b).x +
					  e.xxx*map( pos + e.xxx ,a,b).x );

}


mat3 setCamera( in vec3 ro, in vec3 ta, float cr )
{
	vec3 cw = normalize(ta-ro);
	vec3 cp = vec3(sin(cr), cos(cr),0.0);
	vec3 cu = normalize( cross(cw,cp) );
	vec3 cv =          ( cross(cu,cw) );
    return mat3( cu, cv, cw );
}

vec3 light_equation(vec3 p, vec3 n, vec3 albedo, vec3 lc, float l, float ref) {
    vec3 light_pos = p + l * vec3(.0, .0, 1.);
    float ndotl = max(.1, dot(-n, normalize(light_pos - p) ));
    return (lc+.3) * albedo * 3. * abs(n.y);
    return  (200.*lc*ndotl+1.5)*albedo;
}

vec3 render( in vec3 ro, in vec3 rd )
{
    vec3 col = vec3(.0f);
    vec3 lc;
    float mat = 0.;
    vec2 res = castRay(ro,rd, lc,false, mat);
    float t = res.x;
	float m = res.y;
    vec3 p = ro + rd * t;
    vec3 p1 = p;
    vec3 n = calcNormal(ro + rd*t);
    //vec3 albedo = tex3D(iChannel0, ro+rd*t + .0*vec3(iTime, iTime, iTime)*n.yzx,n).xxx * vec3(.1, 11., 0.1);
    vec3 albedo = pow(tex3D(iChannel0, ro+rd*t,n).xxx, vec3(2.));
    float l;
    bool le = false;
    float ref_str = 1.;
    vec3 amb = vec3(0.);
    vec3 closest_lc = get_light(p, l, false);
    if (res.x > .0f) {
//    return closest_lc;
        if (res.y == 1.) {
            vec3 ref = reflect(rd, n);
            res = castRay(p, ref, lc, true, mat);
            p = p + ref * res.x;
            n = calcNormal(p);
            closest_lc = get_light(p, l, false) * ref_str;
            le = true;
        }
        if (res.y == 2.) {
            col = lc * 2.;
        } else if (res.y == 3.){
            col = lc;
        }else {
            col = amb + light_equation(p, n, albedo, closest_lc, l, 0.);
            if (mat == 1.)
                col *= 2.;
        }
    }
//    col = vec3(0.);
    col += 4.*rmLight(ro, rd, res.x);
//  col = mix(col, vec3(0.), min(1., res.x * res.x / 500. ) );

   	return vec3(col);
}



void main( )
{
    vec2 mo = vec2(0);//iMouse.xy/iResolution.xy;
	float time = .0f; //iTime;

    // camera
    vec3 ro = vec3(.0f, .0f, -4.0f + iTime * 4. * tmul);//vec3( 4.6*cos(0.1*time + 6.0*mo.x), 1.0 + 2.0*mo.y, 0.5 + 4.6*sin(0.1*time + 6.0*mo.x) );
    vec3 ta = vec3( -0.5, -0.4, 0.5 );
    // camera-to-world transformation
    mat3 ca = setCamera( ro, ta, 0.0 );

    vec3 tot = vec3(0.0);
/*
    vec2 k = vec2(gl_FragCoord.xy);
    k = vec2(k * vec2(1., 2.));
    k.x = k.x * 2. + 0. * iResolution.x;
    vec2 p = (-iResolution.xy + 1.0*vec2(k))/iResolution.y;
*/
    vec2 k = vec2(gl_FragCoord.xy);
    k = vec2(k * 2 + stride);
    vec2 p = (-iResolution.xy + 1.0*vec2(k))/iResolution.y;

    // ray direction
    vec3 rd = normalize( vec3(p.xy,2. - min(1., low1 * 1.5) ) );

    // render
    vec3 col = render( ro, rd );
	// gamma
  /*  if (rd.x != 12.312)
    col = vec3(0.);
    if (mod(int(fragColor.x), 2 )  == 0)
        col = vec3(1);
*/
    col = pow( col * 2., vec3(0.8545) );
 //   if (stride > 0. && col.x != 312.312)
   //     col = vec3(0.);
    tot += col;

    fragColor = vec4( tot + stride / 1000., 1.0 );
}
