#version 330 core
layout (location=0) out vec4 fragColor;

uniform float onTempo;
uniform float tick;
uniform float decaying_kick;
uniform float iTime;
uniform vec2 iResolution;

float hash1( vec2 p )
{
    p  = 50.0*fract( p*0.3183099 );
    return fract( p.x*p.y*(p.x+p.y) );
}

float hash1( float n )
{
    return fract( n*17.0*fract( n*0.3183099 ) );
}

float noise( in vec2 x )
{
    vec2 p = floor(x);
    vec2 w = fract(x);
    vec2 u = w*w*w*(w*(w*6.0-15.0)+10.0);

    float a = hash1(p+vec2(0,0));
    float b = hash1(p+vec2(1,0));
    float c = hash1(p+vec2(0,1));
    float d = hash1(p+vec2(1,1));
    
    return -1.0+2.0*(a + (b-a)*u.x + (c-a)*u.y + (a - b - c + d)*u.x*u.y);
}

// Rotation matrix around the X axis.
mat3 rotateX(float theta) {
    float c = cos(theta);
    float s = sin(theta);
    return mat3(
        vec3(1, 0, 0),
        vec3(0, c, -s),
        vec3(0, s, c)
    );
}

// Rotation matrix around the Y axis.
mat3 rotateY(float theta) {
    float c = cos(theta);
    float s = sin(theta);
    return mat3(
        vec3(c, 0, s),
        vec3(0, 1, 0),
        vec3(-s, 0, c)
    );
}

// Rotation matrix around the Z axis.
mat3 rotateZ(float theta) {
    float c = cos(theta);
    float s = sin(theta);
    return mat3(
        vec3(c, -s, 0),
        vec3(s, c, 0),
        vec3(0, 0, 1)
    );
}

float hash11( float n )
{
    return fract(sin(n)*43758.5453);
}

vec3 hash13(float n) {
    float n1 = n;
    float n2 = hash11(n);
    float n3 = hash11(n2);
    return vec3(hash11(n1),hash11(n2),hash11(n3));
}
// Identity matrix.
mat3 identity() {
    return mat3(
        vec3(1, 0, 0),
        vec3(0, 1, 0),
        vec3(0, 0, 1)
    );
}
float sdPlane( vec3 p )
{
    return p.y;
}

float sdSphere( vec3 p, float s )
{
    return length(p)-s;
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

float opS( float d1, float d2 )
{
    return max(-d2,d1);
}

float opSs( in float d1, in float d2 )
{
    d1 *= -1.0;
    return (d1 > d2) ? d1 : d2;
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

vec3 k_cross = vec3(0., .9, 0.0)*3.;
vec3 k_screen = vec3(0.01, 0.015, 0.01);
vec3 k_light1 = vec3(.7, 0.2, 0.3);
vec3 k_light2 = vec3(0.3, 0.2, .7);

vec2 getPhase() {
   // return vec2( 3., floor( mod(iTime / 8., 2.) ) );
    return vec2( floor( mod(iTime / 16., 4.) ),  floor( mod(iTime / 8., 2.)) );
}

float sdCross(vec3 p, vec2 s) {
        vec3 dim = vec3(1.5,
                     .6,
                     .33123405437896355);
                
    vec3 dim2 = dim * vec3(1.1 + s.x , 1. + s.y + .3, dim.z);
    
    float s1 = sdBox(p, dim.xyz );
    float s2 = sdBox(p, dim.yxz );
    
    float core_cross = opU(vec2(s1), vec2(s2)).x;
    
    s1 = sdBox(p, vec3( dim2.xy, dim.z * 1.1) );
    s2 = sdBox(p, vec3( dim2.yx, dim.z * 1.1) );
    
    float core_anticross = opU(vec2(s1), vec2(s2)).x;
    
    float ret = opS(core_cross, core_anticross);
    return ret;
}

float mapSphericalPill(vec3 p, out vec3 id) {


    p.y +=1.2;
    p.xy -= vec2(-0.2, 1.) * abs( pow ( sin(onTempo * 2.), 3.) ) / 2.;
    p.z -= 4.;
    p *= rotateZ(sin( iTime  * 4.) / 6. +abs( pow ( sin(onTempo * 2.), 3.) ) / 6.);
//    p *= rotateX(sin( iTime  * 15.) / 20. );
    
    vec3 s = vec3(1., 5., .5) * 1.2;
    float size = .5;
    id.x = 5.;
    id.y = smoothstep( .7, .06, abs(p.x));

    return length(p * s) - size;
}

float mapPill(vec3 p, out vec3 id, float in_id) {
    p.z-=3.;
    id.x = 1.;
    p *= rotateZ(iTime * 8. + in_id * 21.4 + tick / 3.);
   // p *= rotateY(iTime * 12.+ in_id * 2111.4);
    
    float s = sdCapsule( p, vec3(-.1, .0, 0.),vec3(.1, 0., 0.) , .09);
    id.y = step(p.x, 0.) * in_id;
    
    return s;
}

float mapPillField(vec3 p, out vec3 id) {
    vec3 o = vec3(.0, .0, 10.);
    float speed = 20.;
    vec3 tmp_id;
  
    if(length(p.xy) > 7.5)
        return 1e10;
  
    float rep = 2.;
    
    p.z -= 15. - iTime * 32.;
    vec2 u = floor(p.xy / rep);
    float i =  hash11( u.x * fract( sin(u.x+u.y)) + floor(p.z / 25.));

    p.xy = mod(p.xy, rep) - vec2(rep / 2.);
    float offset = i * 14.;
    p.z = mod(p.z, 25.) - 12.5;
    p.z+=offset;
    vec3 s = vec3(( (3. + decaying_kick / 3.)));
    float d = mapPill(p / s, id, i );
    return d;
}

vec3 path(float time, float z) {
    if (getPhase().x != 0.) 
        return vec3(0.);
    vec3 p = vec3(0.);
    float t = length(z - 1.);

    p.y += sin(t / 20.) * 4. * pow( sin(iTime / 1.), 3.);
    p.x += sin(t /20.) * 4. * pow( sin(1.+iTime / 1.), 3.);

    p.y += sin(t / 20.) * 2. * pow( sin(.2+iTime / .5), 3.);
    p.x += sin(t /20.) * 2. * pow( sin(1.+iTime / .5), 3.);

    p.y += sin(t / 20.) * 1. * pow( sin(.4+.2+iTime / .25), 3.);
    p.x += sin(t /20.) * 1. * pow( sin(1.+iTime / .25), 3.);

    return vec3(p);
}

float sdLights(vec3 p, out vec3 id, out float dlight2) {
    p += path(iTime, p.z);
    p.z-=30.;
    float s = .3;
    float rotSpeed = 4.;
    float rotAmp = 15.;
    vec3 p1 = p, p2 = p;
    
    p1.x += .5*sin(iTime * rotSpeed) * rotAmp;
    p1.z += cos(iTime * rotSpeed) * rotAmp;
    
    p2.z += sin(iTime * rotSpeed + .57) * rotAmp * 1.;
    p2.x += .5*cos(iTime * rotSpeed + .57) * rotAmp;
    
    float d1 = length(p1) - s;
    d1 = sdCross(p1 * 1.2, vec2(-.1, -0.5));
    float d2 = length(p2) - s;
    d2 = sdCross(p2 * 1.2, vec2(-.1, -0.5));

    id.x = 4.;
    id.y = step(d1, d2);
    dlight2 = max(d1,d2);
    return min(d1, d2);
}

float sdCross2D(vec2 uv, float s) {
    
    if (getPhase().x != 2.)
        s = 1.;

    vec4 dim = vec4(0.85, 0.3, 0.2, 0.1) * s;
    vec4 dim_inside = vec4(0.85, 0.3, 0.2, 0.1) * s;
    float smoothness = .01;
    
    float d1 = smoothstep(dim.x, dim.x - smoothness, abs( uv.x ) );
    d1 *= smoothstep(dim.y, dim.y - smoothness, abs( uv.y ) );
 
    float d2 = smoothstep(dim.y, dim.y - smoothness, abs( uv.x ) );
    d2 *= smoothstep(dim.x, dim.x - smoothness, abs( uv.y ) );
 
    return 1.-step(d1+d2, 0.);
}

mat2 rotate2d(float a) {
    return mat2(cos(a), sin(a), -sin(a), cos(a));
}

float maze2D(vec2 uv, float t) {
    uv.y += .5;
    vec2 off = vec2(-0.2, 1.) * pow(abs( sin(iTime * 8.)), 9.) / 2000.;
    uv -= off / 4.;
    uv *= rotate2d(sin(iTime * 2.) / 5.);

  //  uv.xy += texture(iChannel1, uv.xy * 100. + vec2(iTime)).xx / 6.;
    float d1 = smoothstep(.7, 0.0, abs( uv.x / (uv.y) ));
    d1 *= smoothstep(1.5, .3, uv.y);
    d1 *= step(-.0, uv.y);
    d1 *= noise(uv.xy*51.2 + vec2(25., -iTime * 100.));
//    d1 -= min(1.,pow( noise( uv.xy / 20.1 + vec2(0., -iTime)), 1.5 ));
    
    return d1;
}

float rotatingCross2Dfield(vec2 uv, float t) {

    vec2 p1 = uv + vec2 ( .54, .0 );
    vec2 p2 = uv + vec2 ( -.54, .0 );
    vec2 p3 = uv + vec2 ( 0, .54 );
    vec2 p4 = uv + vec2 ( 0, -.54 );

    vec2 dir1 = vec2(1., 0.);
    vec2 dir2 = vec2(-1., 0.);
    vec2 dir3 = vec2(0., 1.);
    vec2 dir4 = vec2(0., -1.);
    
    mat2 r = rotate2d(- 8.* iTime);
    float d1 = sdCross2D(p1 * r +dir1 * (t) * r , .25 * (1.- t*3.));
    float d2 = sdCross2D(p2 * r+ dir2 * (t) * r, .25 * (1.- t*3.) );
    float d3 = sdCross2D(p3 * r+ dir3 * (t) * r, .25 * (1.- t*3.));
    float d4 = sdCross2D(p4 * r+ dir4 * (t) * r, .25 * (1.- t*3.) );
    
    return d1 + d2 + d3 + d4;
}


float mapCrossField(vec3 p, vec3 ro) {
  
    float zdiff = length(ro.z - p.z);
    p+=path(iTime, p.z);

    float l = iTime * 24;
    if (getPhase().x == 1.) {
        l = mod(l,13.5);
    }

    if (getPhase().x >= 2.)
    {
        l = 11.5;
    }

    p.z += l;

    vec3 prep = p;
    float rep_size = 5.5;

    if (getPhase().x == 0.)
       p.z = mod(p.z, rep_size) - rep_size / 2.; 
    else
       p.z -= 15.;

    float s = 1.;
    float scale = (1. + tick * .5 * smoothstep(55., 5., abs(zdiff - 50.)) );
    scale = 1.;
    p.z += tick*1e-10;
    return sdCross(p / vec3(scale/s, scale/s, 1.), vec2( -.1, -0.5 ));
}

float crossfield2d(vec2 uv) {

    if (abs(uv.x) < .9)
        return 0.;
    
    uv *= 3.;
    uv.x += .48;
    float rep = 1.;
    uv.y -= iTime * 6.;
    vec2 ids = floor(uv * rep);
    
    float id = hash11(ids.x);
    uv = mod(uv, rep) - rep / 2.;
    
    return sdCross2D(uv * 2.5, 1.);
}

vec2 map( in vec3 pos, out vec3 id, vec3 ro )
{
    vec3 tmp_id;
    vec2 res = vec2( 1e10, -42.0 );
    float d;
     
    id.z = 0.;
    if ((d = mapCrossField(pos, ro)) < res.x) {
        res.x = d;
        id.x = 0.;
        id.z = 1.;
    }

    if ((d = mapPillField(pos, tmp_id)) < res.x && ( getPhase().x == 1.
    || getPhase() == vec2(3., 1.) ) ) {
           id = tmp_id;
           res.x = d;
           id.z = 1.;
    }
    float k;
    if ( (d = sdLights(pos, tmp_id, k)) < res.x) {
        if (getPhase() == vec2(0., 1.)) {
            res.x = d;
            id = tmp_id;
        }
    }
    if ( (d = mapSphericalPill(pos, tmp_id) ) < res.x ) {
        if ( getPhase().x == 3. ) {
           id = tmp_id;
           res.x = d;
        }
    }

    return res;
}

vec2 castRay( in vec3 ro, in vec3 rd, out vec3 id )
{
    vec2 res = vec2(-1.0,-1.0);

    float tmin = 0.0;
    float tmax = 100.0;
    int steps = 80;
    if (getPhase().x == 0.) 
        steps = 120;
    // raymarch primitives   
    {
    
        float t = tmin;
        for( int i=0; i<steps && t<tmax; i++ )
        {
            vec2 h = map( ro+rd*t, id, ro );
            if( abs(h.x)<(0.0001*t) )
            { 
                res = vec2(t,h.y); 
                 break;
            }
            t += h.x * 1.;
        }
    }
    
    return res;
}

mat3 setCamera( in vec3 ro, in vec3 ta, float cr )
{
	vec3 cw = normalize(ta-ro);
	vec3 cp = vec3(sin(cr), cos(cr),0.0);
	vec3 cu = normalize( cross(cw,cp) );
	vec3 cv =          ( cross(cu,cw) );
    return mat3( cu, cv, cw );
}

vec4 render( in vec3 ro, in vec3 rd , vec2 uv)
{ 
    vec3 col = vec3(.0f);
    vec3 id;
    vec2 res = castRay(ro,rd, id);
    float t = res.x;
	float m = res.y;
    vec3 albedo = vec3(0., 0., 0.);
    vec3 tmp_id;
    float dLight2;
    float dLight1 = sdLights(ro+rd*t, tmp_id, dLight2);

    if (res.x > .0f) {
        if (id.x == 0.) {
            albedo = k_cross;
        }
        if (id.x == 1.) {
            albedo = vec3(1.);
            if (id.y > 0.) {
                albedo = 15.*pow( hash13(id.y) /20., vec3(.85));
            }
        }
        if (id.x == 3.) {
           albedo = k_screen;
        }
        if (id.x == 4.) {
            if (id.y == 0.) {
                albedo = k_light1/.1;
            } else { 
                albedo = k_light2/.1;           
            }
        }
        if (id.x == 5.) {
            albedo = vec3(.8);
            if (id.y == 1.) {
                albedo = vec3(1) / 2.;
            }
        }
    }
    
    float falloff = 3.0;
    float bias = 15.5;
    float intensity = 5.1;
    float pmul = 1.;
    vec3 lCol = ( intensity / pow( 1.+ dLight1 / bias, falloff)) * k_light1 +
    ( 1. / pow( 1. + dLight2 / bias, falloff)) * k_light2;
    if (getPhase().x == 3.) {
        lCol = vec3( 0. );
    }
    if (getPhase() == vec2(0., 1.)) {
        pmul = .2;
    }
    vec3 a = albedo * min(1., -.3+res.x) * pmul + lCol * step(.2, albedo.g) / pmul;

    // 2D Effects 
    if (getPhase().x == 2.) {
        a.xyz+=vec3(sdCross2D(uv.xy, abs( pow ( sin(onTempo * 1.), 3.) )) ) * k_cross;
        a.xyz+=vec3(rotatingCross2Dfield(uv.xy, abs( pow ( sin(onTempo * 1.), 3.) )) ) * k_cross;
        
    } else if ( getPhase().x == 3. ) {
       a.xyz += vec3(maze2D(uv, 0.));
       a.xyz += crossfield2d(uv) * k_cross;
    }
    // 2D Effects end

   	vec4 ret = vec4(a.x, a.y,a.z, id.z);
    return ret;
}

vec3 retro_filter(vec2 uv, vec3 col) {
    float rep_size = .015;
    vec2 uv_rep = mod(uv, vec2(rep_size)) - rep_size / 2.;
    
    float l = length(uv_rep);
    float circle = smoothstep(0.5 * .015, 0.2* .015, l);
    return circle * col;
}

void main(  )
{
    vec3 ro = vec3(.0f, .0f, .0f);
    vec3 ta = vec3( -0.5, -0.4, 0.5 );

    mat3 ca = setCamera( ro, ta, 0.0 );

    vec3 tot = vec3(0.0);
   
    vec2 p = (-iResolution.xy + 2.0*gl_FragCoord.xy)/iResolution.y;

    // ray direction
    vec3 rd = normalize( vec3(p.xy,2.) );

    // render	
    vec4 colid = render( ro, rd, p );
    
    vec3 col = colid.xyz;

    col = retro_filter(p, col);

    col = pow( col, vec3(0.9545) );
    tot += col;

    fragColor = clamp(vec4( tot * 1., 1.0 ), vec4(0.), vec4(1.));
}
