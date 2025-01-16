#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform float energy;
uniform float energy_fast;
uniform float energy_fast2;
uniform float energy_mid;
uniform float energy_slow;
uniform float turfu;
uniform float tic_tile;
uniform vec4 trigger;
uniform float mode;


mat3 m = mat3( 0.00,  0.80,  0.60,
              -0.80,  0.36, -0.48,
              -0.60, -0.48,  0.64 );
float hash( float n )
{
    return fract(sin(n)*43758.5453);
}

vec2 hash22( vec2 p )
{
    //p = mod(p, 4.0); // tile
    p = vec2(dot(p,vec2(175.1,311.7)),
             dot(p,vec2(260.5,752.3)));
    return fract(sin(p+455.)*18.5453);
}


float noise( in vec3 x )
{
    vec3 p = floor(x);
    vec3 f = fract(x);

    f = f*f*(3.0-2.0*f);

    float n = p.x + p.y*57.0 + 113.0*p.z;

    float res = mix(mix(mix( hash(n+  0.0), hash(n+  1.0),f.x),
                        mix( hash(n+ 57.0), hash(n+ 58.0),f.x),f.y),
                    mix(mix( hash(n+113.0), hash(n+114.0),f.x),
                        mix( hash(n+170.0), hash(n+171.0),f.x),f.y),f.z);
    return res;
}

float sdTriangle( in vec2 p, in vec2 p0, in vec2 p1, in vec2 p2 )
{
    vec2 e0 = p1 - p0;
    vec2 e1 = p2 - p1;
    vec2 e2 = p0 - p2;

    vec2 v0 = p - p0;
    vec2 v1 = p - p1;
    vec2 v2 = p - p2;

    vec2 pq0 = v0 - e0*clamp( dot(v0,e0)/dot(e0,e0), 0.0, 1.0 );
    vec2 pq1 = v1 - e1*clamp( dot(v1,e1)/dot(e1,e1), 0.0, 1.0 );
    vec2 pq2 = v2 - e2*clamp( dot(v2,e2)/dot(e2,e2), 0.0, 1.0 );
    
    float s = e0.x*e2.y - e0.y*e2.x;
    vec2 d = min( min( vec2( dot( pq0, pq0 ), s*(v0.x*e0.y-v0.y*e0.x) ),
                       vec2( dot( pq1, pq1 ), s*(v1.x*e1.y-v1.y*e1.x) )),
                       vec2( dot( pq2, pq2 ), s*(v2.x*e2.y-v2.y*e2.x) ));

    return -sqrt(d.x)*sign(d.y);
}

vec3 saturate(vec3 x)
{
    return clamp(x, vec3(0.0), vec3(1.0));
}


float sdCross(vec2 p) {
    p *= 2.;
    vec2 p2 = vec2(p.y, p.x);
    p2.y = abs(p2.y);
    p2.y -=.0;
    p.y = abs(p.y);
    p.y-=.0;

    vec2 v1 = vec2(-.5, 0.);
    vec2 v2 = vec2(.5, 0.);
    vec2 v3 = vec2(0., 1.5);
    float sd1= sdTriangle(p, v1, v2, v3);
    float sd2 = sdTriangle(p2, v1, v2, v3);
    return min(sd1, sd2);

}

 
mat2 rotate2d(float _angle){
    return mat2(cos(_angle),-sin(_angle),
                sin(_angle),cos(_angle));
}

float sdStar(vec2 p) {
    float d1 = sdCross(p);
    float d2 = sdCross(rotate2d(3.14 / 4.) * p  );
    return min(d1, d2);
}


float opExtrusion( in vec3 p, in float h )
{
    float d = sdStar(p.xy);
    vec2 w = vec2( d, abs(p.z) - h );
    return min(max(w.x,w.y),0.0) + length(max(w,0.0));
}


float c2() {
    return 0.;
    return .1*clamp(.0, 1., clamp(-.2, .2, sin(iTime / 3. + .7) ));
}

float hash31(vec3 p) {
    float h = dot(p,vec3(127.1,311.7, 21.));	
    return fract(sin(h)*43758.5453123);
}

float hash21( vec2 p ) {
    float h = dot(p,vec2(.1124,.76542));    
    
    return fract(sin(h)*22.54531);
}

vec3 pal( in float t, in vec3 a, in vec3 b, in vec3 c, in vec3 d )
{
    return a + b*cos( 6.28318*(c*t+d) );
    
}
 
vec3 HUEtoRGB(in float hue)
{
    hue += iTime / 8;
    hue = fract(hue);
    vec3 rgb = abs(hue * 6. - vec3(3, 2, 4)) * vec3(1, -1, -1) + vec3(-1, 2, 2);
    return clamp(rgb, 0., 1.);
}

float path(float t) {
    return 0.1;
}

float multiwave(float path) {
    path /= 3.;
    return 10.*(2. * sin(path / 40.) + 
            4. * sin(path / 16.)+
            1. * sin(path/8.)+
            1. * sin(path/10.));
}
float dmultiwave(float path) {
    path /= 3.;
    return 10.*(2./40. * cos(path / 40.) + 
            1./4. * cos(path / 16.)+
            1./8. * cos(path / 8. )+
            1./10. * cos(path/ 10. ));
}

float opS( in float d1, in float d2 )
{
    d1 *= -1.0;
    return (d1 > d2) ? d1 : d2;
}


vec3 archCOL(vec3 p ) {
    float rep = 52.;
    float size = 11.;
    float in_size = 7.8;
    float l = 25.5;
    p.y += multiwave(p.z);
    float id = floor(p.z / rep);
    p.z = mod(p.z, rep) - rep / 2.;
    p.z-=20.;
    float outer = length(p.xy) - size;
    float iner = length(p.xy) - size + .5;
    float d = opS(iner, outer);
    
    float dist = max(d, abs( p.z - l) );
    vec3 c =  HUEtoRGB(hash31(vec3(id)));
    c /= 4.;
    c+= .3;
    return c;
}

float mapArch(vec3 p) {
    float rep = 52.;
    float intset = 7.8 + energy_fast2*15.;
    float size = intset + 3.2;
    float in_size = intset;
    float l = -25.5;
    p.y += multiwave(p.z);
    p.z = mod(p.z, rep) - rep / 2.;
    p.z-=20.;
    float outer = length(p.xy) - size;
    float iner = length(p.xy) - size + .5;
    float d = opS(iner, outer);
    
    float step = smoothstep(0., 1., abs(p.z-l) - d);

    return max(d, abs( p.z - l)) - ((mode == 1) ? energy_fast*.5 : energy_fast*2.5);
}

float mapFence(vec3 p) {
    float rep = 2.;
    float height = .4;// + (1.+ sin(p.z / 4.)) / 1.;
    float size = .1 ;
    
    p.y += multiwave(p.z);
    p.z = mod(p.z, rep) - rep / 2.;
    p.x = abs(p.x) - 12.;
    float dt = length(vec2(p.x, p.y -.76 - height + 4.0*size)) - size / 2.;
    dt = min(dt, length(vec2(p.x, p.y - height + 4.0*size)) - size / 2.);
        
    vec3 pstar = vec3(p.z, p.y, p.x);
    //float dstar = opExtrusion(pstar, .01);
    float dstar = length(pstar)-.5;
    float df = abs(max(length( p.xz - size), -.1+abs(p.y +.8) - height));
    return min(dt, dstar);
    
}

float mapRoad(vec3 p, out vec2 id) {
 
    vec2 rep = vec2(1, 1.);
    
    vec2 mp = mod(p.xz, rep) - rep / 2.;
    
    float s = .35;
    id.x = fract( ((+ p.z/rep.y)*0.323 + (p.x / rep.x )) *.0379523 );
   
    id.y = hash21( (floor(p.xz / rep.xy )+vec2(0., tic_tile)) * 10.  );
    if (id.y < 0.4)
    id.x = fract( (floor(+ p.z/rep.y) *0.323+ floor(p.x / rep.x )) *0.0379523 );
    float l = iTime* 2. * hash21( floor(p.xz / rep)  );
    
    p.y -= .3 + sin(l ) * .0;
    float h =  p.y + 2. + multiwave(p.z);
    
    
    h += cos(sin(p.z * .2 + p.x * .2  + trigger.x*2.) + p.x / 3.)*energy*1.;

    return max( max(max(mp.x -s , mp.y - s ) , abs(p.x) - 12. ), abs( h )  - .05);
}

vec2 map(vec3 p, out vec2 id) {
    vec2 id2;
    vec3 ps = p;
    p.x += sin(p.z / 200.) * 400.;
    vec2 res =  vec2(mapRoad(p, id), 1.);
    
    
    vec2 resFence = vec2(mapFence(p), 2. );
    if (resFence.x < res.x) {
        res = resFence;
    }
    
    vec2 resArch = vec2(mapArch(p), 3.);
    if (resArch.x < res.x) {
        res = resArch;
    }
<<<<<<< HEAD
    //vec2 resStar = vec2(mapStarField(ps, id2), 4.);
    //if (resStar.x < res.x) {
    //    res = resStar;
    //    id = id2;
    //}
=======
>>>>>>> 84cc3a7 (Add blend from luminance improve 3d renderer change rainbow road + mega banger)
    return res;
}

vec2 mapArch(vec3 p, out vec2 id) {
    vec2 id2;
    vec3 ps = p;
    p.x += sin(p.z / 200.) * 400.;
    vec2 resArch = vec2(mapArch(p), 3.);
    return resArch;
}


vec2 castRay(vec3 ro, vec3 rd, out vec2 id) {
    vec2 res = vec2(1e10, 0.);
    vec3 pos = ro;
    vec2 tmp = vec2(1.,0.)*.01;
    const float NEAR = 0.;
    float FAR = (mode == 1) ? 220. : 440.;

    float t = NEAR;
    
    for (int i = 0; i < 300 && t < 600; ++i) {
    
        pos = ro + rd * t;
        
        vec2 h = (mode == 1) ? map(pos, id) : mapArch(pos, id);
        if (abs(h.x) < 0.001* t) {
            res = vec2(t, h.y);
            break ;
        }
        t += h.x*.5;
    }
    
    return res;
}


vec3 normal (in vec3 p)
{
    vec2 e = vec2(.0001, .0);
    vec2 id;
    float d = map (p,id).x;
    vec3 n = vec3 (map (p + e.xyy,id).x - d,
                   map (p + e.yxy,id).x - d,
                   map (p + e.yyx,id).x - d);
    return normalize(n);
}

vec3 normal_arch (in vec3 p)
{
    vec2 e = vec2(.0001, .0);
    vec2 id;
    float d = mapArch(p,id).x;
    vec3 n = vec3 (mapArch(p + e.xyy,id).x - d,
                   mapArch(p + e.yxy,id).x - d,
                   mapArch(p + e.yyx,id).x - d);
    return normalize(n);
}

vec3 raymarch_arch(vec3 ro, vec3 rd) {
    float t = 0.;
    vec3 acc = vec3(0.);
    for (int i = 0; i < 40; ++i) {
        vec3 pos = ro + rd * t;
        float dLight = .1+21.5/(10.+ length(mod(pos.zzz, 52.) -10.))*0.5;
        acc += dLight * archCOL(pos) / 50.;
    }
    return vec3(acc);
}

float stars(vec2 uv) {
    return 0.;
    float acc = 0.;
    float s = 0.1;
    float scale = 100.;
    for (float i = 0.; i < 3.; i = i + 1.) {
        for (float j = 0.; j < 3.; j = j + 1.) {
            vec2 off = vec2( (j - 2.) * s, (i - 2.) * s);  
            acc += ( smoothstep( .92, 1.0, pow( noise(vec3( uv.x * scale + off.x, uv.y * scale + off.y, 0.)),3. )));
        }
    }
    return acc / 20.;
}

vec3 render(vec3 ro, vec3 rd, vec2 uv) {

    vec2 id;
    vec2 res = castRay(ro, rd, id);
    vec3 pos = ro + rd * res.x;
    float mat = res.y;
    float depth = length(pos - ro);
    vec3 albedo = vec3(10.);
    vec3 nor = normal(pos);

    vec2 tmp = vec2(1.,0.)*50.;

    vec3 lightDir = normalize( vec3(-2., 1., -0.));

    float ndotl = max(.4, dot(nor, lightDir));

    vec3 stars = vec3(stars(vec2(uv.x, rd.y)));

    float dLight = .03+21.5/(5.+ length(mod(pos.zzz, 52.) -20.))*0.05;
    vec3 dLightCol = archCOL(pos)*(.6+energy_mid*20.);

    if (mat == 0.) {
        return stars;
    }
    if (mat == 1. || mat == 4.) {
        albedo = 12.* HUEtoRGB(id.x);// * (texture(iChannel1, pos.xz * 11.).x * 3. + .1);
        if (id.y < 0.02)
        albedo *= 32.;
        if (mat == 4.)
        albedo *= 40.;
     }
    if (mat == 2.) {
        albedo = vec3(0.5, 0.5, 0.2) * 20.;
    }
    float f = 1. / (1. +pow(depth * .0015 , 2.));

    float m = clamp(0., 1., 1.7 - f);
    return vec3(mix(dLightCol*dLight*albedo *ndotl + albedo / 30., stars  * 4., .8));
}

void camera(out vec3 ro, out vec3 rd, vec2 uv) {
    float speed = iTime * 7.5;
    ro = vec3( + sin(speed / 200.) * 400., 3.0 + multiwave(speed), -speed);
    vec2 mouse = vec2(0.);
    mouse.y += 3.;
    vec3 lookAt = vec3(
                       sin(speed / 200.) * 400. - 2.*cos(speed/200.)*(1.-turfu)
                                + mouse.x + uv.x,
                       mouse.y + -uv.y + multiwave(speed)- dmultiwave(speed)*(1.-turfu)*.25, 
                       (1.-turfu)-speed);
    
    rd = normalize(ro - lookAt);
    
}

void main()
{
    // Normalized pixel coordinates (from -1 to 1)
    vec2 uv = (-iResolution.xy + 2.0*gl_FragCoord.xy)/iResolution.y;
    vec3 ro, rd;
    camera(ro, rd, uv);
    vec3 col = pow( render(ro, rd, uv)*1.6, (turfu == 0.3) ? vec3(energy*3.) : vec3(energy_slow*4.));
    fragColor = vec4(pow(col, vec3(1.0))/1.,1.0);
}


