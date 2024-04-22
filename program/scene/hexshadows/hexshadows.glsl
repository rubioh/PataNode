#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;

mat2 rotate2d(float _angle){
    return mat2(cos(_angle),-sin(_angle),
                sin(_angle),cos(_angle));
}

vec3 pal( in float t, in vec3 a, in vec3 b, in vec3 c, in vec3 d )
{
    return a + b*cos( 6.28318*(c*t+d) );
}


vec3 hash13(float p) {
    float d = dot(        vec3( p*231.4213,
        p*76.123,
        p*998.872 )
, vec3(12.23, 321.2, 321.98));


return fract(sin(vec3(
            d/3.312,
            d/7.321,
            d/9.321
        )
    ) );
}

// More concise, self contained version of IQ's original 3D noise function.
float noise3D(in vec3 p){
    
    // Just some random figures, analogous to stride. You can change this, if you want.
	const vec3 s = vec3(113, 157, 1);
	
	vec3 ip = floor(p); // Unique unit cell ID.
    
    // Setting up the stride vector for randomization and interpolation, kind of. 
    // All kinds of shortcuts are taken here. Refer to IQ's original formula.
    vec4 h = vec4(0., s.yz, s.y + s.z) + dot(ip, s);
    
	p -= ip; // Cell's fractional component.
	
    // A bit of cubic smoothing, to give the noise that rounded look.
    p = p*p*(3. - 2.*p);
    
    // Standard 3D noise stuff. Retrieving 8 random scalar values for each cube corner,
    // then interpolating along X. There are countless ways to randomize, but this is
    // the way most are familar with: fract(sin(x)*largeNumber).
    h = mix(fract(sin(h)*43758.5453), fract(sin(h + s.x)*43758.5453), p.x);
	
    // Interpolating along Y.
    h.xy = mix(h.xz, h.yw, p.y);
    
    // Interpolating along Z, and returning the 3D noise value.
    float n = mix(h.x, h.y, p.z); // Range: [0, 1].
	
    return n;//abs(n - .5)*2.;
}

vec3 hash23(vec2 p) {
    return fract(sin(vec3(p.x * 123.2, p.y * 1323.31, p.x*p.y * 211.99)) );
}

float hash21(vec2 p){
   
    float n = dot(p, vec2(7.163, 157.247)); 
    return fract(sin(n)*43758.5453);
}

float hash11(float p) {
    return hash21(vec2(p));
}

vec3 fhash13(float p) {
    return hash23(vec2(p));
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

const vec2 s = vec2(.866025, 1);
#define ZERO (min(0,0))


float sdHexagon(vec2 p, float h, vec3 b, float id) {
    //h +=  texture(iChannel2, p.xy / 12.).r / 5. * id;
    p = abs(p);
    p = vec2(p.x*.866025 + p.y*.5, p.y);
    float d1 = length(max(abs( vec3( p.x, h, p.y )) - b + .015, 0.)) - .0025;
    b.xz/=1.5;
    h -=.01;
    
    //b.y += sin(4. * iTime + id * 12.) * id / 3.;
    float d2 = length(max(abs( vec3( p.x, h, p.y )) - b + .015, 0.)) - .0025;
    b.xz/=1.5;
    h -=.01;
   // b.y += 1.;
   
    float d3 = length(max(abs( vec3( p.x, h, p.y )) - b + .015, 0.)) - .0025;
    //return d1;
    d1 =  min(d1, d2);
    return d1;
    return min(d1, d3);
}

float sdHexagonS(vec2 p, float h, vec3 b, float id) {
    //h +=  texture(iChannel2, p.xy / 12.).r / 5. * id;
    p = abs(p);
    p = vec2(p.x*.866025 + p.y*.5, p.y);
    float d1 = length(max(abs( vec3( p.x, h, p.y )) - b + .015, 0.)) - .0025;
    b.xz/=1.5;
    h -=.1;
    return d1;
}


vec4 getCellData(vec2 cellID, float y,  float fall) {
    float h;
    
    h = noise3D( vec3(cellID.xy + vec2(iTime / 2., 0.), 0.*(iTime / 1.)) ) * .8;
    float k = 0.;
    if (length(cellID/12.) > .3) {
     ;//   k = 1e10;
    }

    return vec4(-(h*h), hash21(cellID), cellID.x, k);
}

vec4 mapC(vec3 p) {

    float s = .1;
    float r = 1.5;
    float sdr = .2;
    vec3 b = vec3(sdr, .1, sdr);
    vec4 ret;
//    ret.y = p.z/12.;
    p.y -= 1.;
    p.xz *= rotate2d(-.7);
    float id = floor(p.x / r);
  
    p.x = mod(p.x, r) - r/2.;
    float r2 = 1.;
      vec3 p2 = p;
    p2.z += id / 5.;
    p2.z = mod(p2.z, r2) - r2 / 2.;
   
    float d2 = sdHexagonS(p2.xy, p2.z, b, 0.);
    p.xy += sin(p.z * 150.) / 301.;
    ret.x =  min(d2, length(p.xy) - s);
    ret.w = 1.;
    if (d2 < length(p.xy) - s) {
        ret.w = 3.;
    }
    //ret.x = min(ret.x, sdHexagonS(p.xz, p.y, b + vec3(-.1, 5., -.1), 0. ));
    return ret;
}

vec4 mapHexagons(vec3 p, float fall) {
   // p.z=iTime;
    float r = .25;
    vec3 b = vec3(r, .5, r);
    p.xz*=2.;
    //p.y -= 2.5;
    vec4 hC = floor(vec4(p.xz, p.xz - vec2(0, .5))/s.xyxy) + vec4(0, 0, 0, .5);
    vec4 hC2 = floor(vec4(p.xz - vec2(.5, .25), p.xz - vec2(.5, .75))/s.xyxy) + vec4(.5, .25, .5, .75);

    // Centering the coordinates with the hexagon centers above.
    vec4 h = vec4(p.xz - (hC.xy + .5)*s, p.xz - (hC.zw + .5)*s);
    vec4 h2 = vec4(p.xz - (hC2.xy + .5)*s, p.xz - (hC2.zw + .5)*s);
    vec4 cellData1 = getCellData(hC.xy, p.y, fall);
    vec4 cellData2 = getCellData(hC.zw, p.y, fall);
    vec4 cellData3 = getCellData(hC2.xy, p.y, fall);
    vec4 cellData4 = getCellData(hC2.zw, p.y, fall);
    
    vec4 dist = vec4(cellData1.w+sdHexagon(h.xy, p.y + cellData1.x, b, hash21(hC.xy) ), cellData2.w+sdHexagon(h.zw, p.y + cellData2.x, b, hash21(hC.zw) ),
    cellData3.w+sdHexagon(h2.xy, p.y + cellData3.x, b, hash21(hC2.xy) ),cellData4.w+sdHexagon(h2.zw, p.y + cellData4.x, b, hash21(hC2.zw) ));

    //vec4 dd = vec4(cellData1.w,cellData2.w,cellData3.w,cellData4.w);
    //dist = max(dd, dist);
    h = dist.x<dist.y ? vec4(h.xy, hC.xy) : vec4(h.zw, hC.zw);
    h2 = dist.z<dist.w ? vec4(h2.xy, hC2.xy) : vec4(h2.zw, hC2.zw);

    vec2 oH = dist.x<dist.y ? vec2(dist.x, 0.) : vec2(dist.y, 0.);
    vec2 oH2 = dist.z<dist.w ? vec2(dist.z, 0.) : vec2(dist.w, 0.);
    vec3 dataRet;
    vec4 DistdataRet;
    
    DistdataRet = dist.x<dist.y ? vec4(dist.x, cellData1.yzw) : vec4(dist.y, cellData2.yzw);
    DistdataRet = dist.z<DistdataRet.x ? vec4(dist.z, cellData3.yzw) : DistdataRet;
    DistdataRet = dist.w < DistdataRet.x ? vec4(dist.w, cellData4.yzw) : DistdataRet;
    dataRet = DistdataRet.yzw;
    //return oH<oH2 ? vec4(h.xy, hC.xy) : vec4(h2.xy, hC2.xy);
    //return oH.x<oH2.x ? vec4(oH,  h.zw) : vec4(oH2, h2.zw);

    vec4 ret =  vec4(min ( min(dist.x, dist.z), min(dist.w, dist.y)) );
    ret.yzw = dataRet;
    return ret;
}

vec4 mapL(vec3 p) {
//
   // p.xz *= rotate2d(p.z / 29.);
    float r = 3.;
    
    p.z+=cos(p.x / 12.) * +12.;
    
    p.x=abs(p.x);
    p.x+= iTime * -6.;
  //  p.x = mod(p.x, r) -r/2.;
    return mapHexagons(p.xzy, 0.);
}
vec4 map( in vec3 pos )
{
    pos.xy*=rotate2d(pos.z / 12.);
    vec4 res = vec4(1e10, 0.0, 0., 0. );
    vec3 pf = pos;
    //pf.y = -abs(pf.y);
    vec4 r2 = mapHexagons(pf + vec3(.0, +2., .0), 0.);
    if (r2.x < res.x) {
        res = r2;
    }
    
    float hole= length( pos - vec3( .4, 0., 5. )) - 2.5;
    vec3 pw = pos;
    pw.z = -pw.z;
    pw.yz *=rotate2d(.5);
    vec4 r3 = mapHexagons(pw.xzy - vec3(0., -2, .0), 0.);
    //r3.x = min(r3.x, hole);
    //r3.x = max(r3.x, - mapC(pos / 2.).x);
    if (r3.x < res.x) {
       res = r3;
    }
    vec3 ps = pos;
    ps.x = -abs(ps.x);
     ps.xy *= rotate2d(-.9);
    vec4 r4 = mapHexagons(ps.zxy - vec3(0., -3., .0), 0.);
    if (r4.x < res.x) {
        res = r4;
    } 
    /*
    vec4 r4 = mapL(pos + vec3(0., 0., -42. + -iTime * 4.));
    
    if (r4.x < res.x)
           res = r4;
           */
    vec4 r5 = mapC(pos);
    if (r5.x < res.x)
        res = r5;
    vec4 r6 = mapC(pos + vec3(0.5, -1., 0.));
    if (r6.x < res.x)
        res = r6;
        
    return res;
}

const float maxHei = 0.8;

vec4 castRay( in vec3 ro, in vec3 rd )
{
    vec4 res = vec4(-1.0,-1.0, 0., 0.);
    vec4 outlineres = vec4(-1.0,-1.0, 0., 0.);
    float tmin = 0.0;
    float tmax = 50.0;

    // raymarch primitives   
    {
    
        float t = tmin;
        for( int i=0; i<100 && t<tmax; i++ )
        {
            vec4 h = map( ro+rd*t );
            if( abs(h.x)<(0.0001*t) )
            { 
                 res = vec4(t,h.yzw); 
                 break;
            }
            t += h.x;
        }
    }

  
    return res;
}

vec3 tex3D( sampler2D tex, in vec3 p, in vec3 n ){
  
    n = max((abs(n) - .2)*7., .001); // n = max(abs(n), .001), etc.
    n /= (n.x + n.y + n.z );  
    
	vec3 tx = (texture(tex, p.yz)*n.x + texture(tex, p.zx)*n.y + texture(tex, p.xy)*n.z).xyz;
    
    return tx*tx;
}
vec3 texBump( sampler2D tx, in vec3 p, in vec3 n, float bf){
   
    const vec2 e = vec2(.001, 0);
    
    // Three gradient vectors rolled into a matrix, constructed with offset greyscale texture values.    
    mat3 m = mat3(tex3D(tx, p - e.xyy, n), tex3D(tx, p - e.yxy, n), tex3D(tx, p - e.yyx, n));
    
    vec3 g = vec3(.299, .587, .114)*m; // Converting to greyscale.
    g = (g - dot(tex3D(tx,  p , n), vec3(.299, .587, .114)))/e.x; 
    
    // Adjusting the tangent vector so that it's perpendicular to the normal -- Thanks to
    // EvilRyu for reminding me why we perform this step. It's been a while, but I vaguely
    // recall that it's some kind of orthogonal space fix using the Gram-Schmidt process. 
    // However, all you need to know is that it works. :)
    g -= n*dot(n, g);
                      
    return normalize( n + g*bf ); // Bumped normal. "bf" - bump factor.
	
}

// https://iquilezles.org/articles/rmshadows
float calcSoftshadow( in vec3 ro, in vec3 rd, in float mint, in float tmax )
{
    // bounding volume
    float tp = (maxHei-ro.y)/rd.y; if( tp>0.0 ) tmax = min( tmax, tp );
    
    float res = 1.0;
    float t = mint;
    for( int i=ZERO; i<16; i++ )
    {
		float h = map( ro + rd*t ).x;
        res = min( res, 8.0*h/t );
        t += clamp( h, 0.02, 0.10 );
        if( res<0.005 || t>tmax ) break;
    }
    return clamp( res, 0.0, 1.0 );
}

// https://iquilezles.org/articles/normalsSDF
vec3 calcNormal( in vec3 pos )
{
    vec2 e = vec2(1.0,-1.0)*0.5773*0.0005;
    return normalize( e.xyy*map( pos + e.xyy ).x + 
					  e.yyx*map( pos + e.yyx ).x + 
					  e.yxy*map( pos + e.yxy ).x + 
					  e.xxx*map( pos + e.xxx ).x );
 
}

float calcAO( in vec3 pos, in vec3 nor )
{
	float occ = 0.0;
    float sca = 1.0;
    for( int i=ZERO; i<5; i++ )
    {
        float hr = 0.01 + 0.12*float(i)/4.0;
        vec3 aopos =  nor * hr + pos;
        float dd = map( aopos ).x;
        occ += -(dd-hr)*sca;
        sca *= 0.95;
    }
    return clamp( 1.0 - 3.0*occ, 0.0, 1.0 ) * (0.5+0.5*nor.y);
}


mat3 setCamera( in vec3 ro, in vec3 ta, float cr )
{
	vec3 cw = normalize(ta-ro);
	vec3 cp = vec3(sin(cr), cos(cr),0.0);
	vec3 cu = normalize( cross(cw,cp) );
	vec3 cv =          ( cross(cu,cw) );
    return mat3( cu, cv, cw );
}
vec3 bumpMap(vec3 n, vec3 tex) {
       return normalize( n );
}

float calcOutline(vec3 pos, vec3 nor) {
    vec4 cellData = map(pos);
    if ( mod( cellData.z, 2.) == 0.)
        return 0.;
    return 1.;
}
vec3 render( in vec3 ro, in vec3 rd )
{ 
    vec3 col = vec3(.0f);
    vec4 res = castRay(ro,rd);
    float t = res.x;
	float m = res.y;
    vec3 p = ro + rd * res.x;
    

    vec3 n = calcNormal(p);
    vec3 tex = vec3(1.);//tex3D(iChannel0, p * 2.,n).xyz;
    //n = texBump(iChannel0, p * 2., n , .05);

//    n = n + normalize( ( tex3D(iChannel0, p * 1112., n) - .5) * 1.);
    //vec4 ref = castRay(p, reflect(normalize(p-ro) , n) );
    vec3 distCol = pal( res.x / 12., vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.3,0.20,0.20) );
    vec3 idcol = pal( res.y /4. + 62.3 / 4., vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(2.0,1.0,0.0),vec3(0.5,0.20,0.25) );
    vec3 posxcol = pal( (p.x /10. + iTime / 2.), vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.0,0.10,0.20) );
    vec3 posycol = pal( (p.y /10. + iTime / 2.), vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.0,0.10,0.20) );
    
    float lt = iTime / 2.;
    
    vec3 lightPos = fhash13(floor( lt  )) *vec3(3.,3., 1.5);
    vec3 plightPos = fhash13(floor( lt  - 1.)) *vec3(3.,3., 1.5);
    lightPos = mix(plightPos, lightPos, fract(lt) );
    vec3 lightCol = 2.*pal( hash11(floor(lt)), vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.0,0.10,0.20) );
    vec3 plightCol = 2.*pal( hash11(floor(lt - 1.)), vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.0,0.10,0.20) );
    lightCol = mix(plightCol, lightCol, fract(lt) );
    float spec = max(0., dot(normalize(p-lightPos), reflect(normalize(ro - p), n )));
    spec = pow(spec, 5.);
    //lightPos = vec3( .4, 0., 2. );
    vec3 albedo = posxcol*posycol + idcol + distCol;//distCol  + idcol + posxcol * posycol;
    if (res.w == 3.) {
        albedo += 1.8*vec3(.7, .3, .1);
    }
    float s = calcSoftshadow(p, normalize(lightPos - p), 0.01, 20. );
    float ao = calcAO(p, n);
    float ndotl = max(0.1, dot(n, normalize(lightPos - p)) );
    albedo = albedo * tex;
    if (res.x > .0f) {
     	col =  albedo* ao * 0.01 + s*albedo*spec+ idcol.xxx*albedo * (ndotl) * lightCol * s;// *(.2 +  calcAO(p,n));
    }
    
   	return vec3(col);
}



void main()
{
    vec2 mo = vec2(0);//iMouse.xy/iResolution.xy;
	float time = .0f; //iTime;

    // camera	
    vec3 ro = vec3(.0f, .0f, -4.0f);//vec3( 4.6*cos(0.1*time + 6.0*mo.x), 1.0 + 2.0*mo.y, 0.5 + 4.6*sin(0.1*time + 6.0*mo.x) );
    vec3 ta = vec3( 0.0, -0.4, 0.0 );
    // camera-to-world transformation
    mat3 ca = setCamera( ro, ta, 0.0 );

    vec3 tot = vec3(0.0);
   
    vec2 p = (-iResolution.xy + 2.0*gl_FragCoord.xy)/iResolution.y;

    // ray direction
    vec3 rd = ca * normalize( vec3(p.xy,2.) );

    // render	
    vec3 col = render( ro, rd );

    // gamma
    col = pow( col, vec3(0.4545) );

    tot += col;

    fragColor = vec4( tot, 1.0 );
}