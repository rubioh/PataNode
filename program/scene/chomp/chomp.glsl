#version 330 core
float vres = 1.5;

layout (location=0) out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float energy_fast;
uniform float energy_mid;
uniform float energy_slow;
uniform float bpm;
uniform float intensity;
uniform float tf;
uniform float scale;
uniform sampler2D iChannel0;
#define PI 3.141593

float time() {
    return iTime / 4.;
}
float noise2( in vec3 x )
{
    vec3 i = floor(x);
    vec3 f = fract(x);
	f = f*f*(3.0-2.0*f);
	vec2 uv = (i.xy+vec2(37.0,17.0)*i.z) + f.xy;
	vec2 rg = textureLod( iChannel0, (uv+0.5)/256.0, 0.0 ).yx;
	return mix( rg.x, rg.y, f.z );
}

vec3 pal( in float t, in vec3 a, in vec3 b, in vec3 c, in vec3 d )
{
    return a + b*cos( 6.28318*(c*t+d) );
}

float hash(float a) {
    return fract( sin(a * 521.12)* 12.312);
}
float sdBox(vec3 p, vec3 o) {
   // p-= o;
    p = abs(p);
    p -= o;
    return max(p.x, max(p.y, p.z) ) - 2.;
}

float wf() {
    float t = time();
    
    float mat = hash(floor( t  ) );
    return floor(mat * 10.);
}

float t() {
    return mod( -time() * 41., 1000.);
}
float chompCount() {
    float t = -1.+floor(time() * 9. / 6.28 + 0.5);
    return t;
}

float chomp() {
    float t = 1.+sin(time() * 9.);
    //float t = energy_fast;
    return pow(t, 4.) / 1.;
}
mat2 r(float a) {
    return mat2(cos(a), -sin(a), sin(a), cos(a));
}

vec4 mapGround(vec3 p) {
p+= ( noise2(p ) - .5 ) * 16.;

vec2 uv = p.xz;
//p.z -= time() * 21.;
p.xy/=1.5;
    p.x += 5.;
    p.xy *= r( p.z / (15. ));
    p.y +=sin(p.x / 20. - 4.5) * 4.;
    float mat = 5.;
    float a = 0.;//texture(iChannel0, uv * .0123  ).r * 5.;
    p.y+=a;
    
    a = p.y;
   
    float d1 = p.y + 17.5;
    float d2 = 30. - p.y;
    float d = min(d1, d2);
      //  d=1e10;
    return vec4(d, mat, a, 0.);
}
vec4 mapHead(vec3 p ) {
p.xy*=1.4;
    p.z -= 55.4 + t() - chomp();
    p.y -= 10. - chomp() / 2.;
    p /= (1.+ chomp() / 50.);
    vec3 pT = p;
    vec3 pEye = p;
    vec3 pMouth = p;
    vec3 pFire = p;
    pMouth.x /= 1.5;
    pMouth.y += cos(p.x / 6. - .0) * (2. + chomp() / 4.);

    pMouth.y *= 1.+chomp();
    p.y*=1.+ chomp()*.01;
    //p.y += cos(p.y);
    p.xy /= 1.3;
    float mat = 1.;
    
    float d1 = length(p) - 16.;
    float d2 = sdBox(p, vec3(10.));
    
    float d = mix(d1, d2, -1. + mod( chompCount() / 2., 2.5));
    
    pEye.z += 25.;
    pEye.x = abs(pEye.x);
    pEye.x -= 5.;
    pEye.y -= 7.;
    
    vec3 pS = pEye;
    pS.x += 2.;
    pS.y -= 6. - chomp() / 10.;

    pS.xy *= r(.0 + -.8 * chomp() / 10.);
    pS.x /= 2.;

    float dEye = length(( pEye )) - 3.;
    
    float dS = length(pS) - 2.;
    if (dEye < d) {
        mat = 3.;
        if (dEye < -.5) {
            //mat = 6.;
        }
    }
    
    d = min(d, dEye);
    if (dS < d) {
        mat = 6.;
    }
    
    d = min(d, dS);
    pFire.z /= 4.;
    pFire.z -= 35.;

    float dFire = length(pFire) - 20.;
    
    if (dFire < d) {
//        mat = 6.;
    }
    
   // d = min(d, dFire);

    pMouth.z += 10.;
    pMouth.y +=5.;
    float dMouth = length(pMouth) - 9.;

    if (-dMouth > d) {
        mat = 4.;
    }
    d = max(d, -dMouth);
  
    pT.y =  abs(pT.y);
    pT.y -= 1.;
    pT.y -= chomp() * 5.;
    pT.z += 11.;
    //pT.y /= 2.;
    float rt = .1;
    pT.x = mod(pT.x, rt) - rt / 2.;
    float dT = length(pT.xz) - 1.1;
    dT = max(dT, pT.y- 3.  );
    dT = max(dT, dMouth );
  if (dT < d) {
        mat = 3.;
    }

    d = min(d, dT);
    return vec4(d, mat, 0., 0.);
}

vec4 mapPath(vec3 p) {
    float mat = 3.;
    float z = p.z - t();
    p.z += 31.;
    float r = 85.5;
    p.z += t() * 2.;
    p.y += sin(p.z);
    p.z = mod(p.z, r) - r/2.;
    float d = length(p.xyz) - 2.5;
    float kk = 3.;
    
    return vec4(d, mat, 0., 0.);
}

vec4 map(vec3 p) {
p/=1.;
    vec4 ret = vec4(1e10, .0, .0, 0.);
    
    vec4 d = vec4(0.);
    
    d = mapHead(p);
    if (d.x < ret.x) {
        ret = d;
    }
    
    d = mapPath(p);
    if (d.x < ret.x) {
        ret = d;
    }
    
    d = mapGround(p);
    if (d.x < ret.x) {
        ret = d;
    }
    return ret;
}

vec3 fc(vec3 p, vec3 rd) {

    vec3 ret;
    float e = 0.0001;
    //p += rd * e;
  //  e = 0.;
    //if (rd.x>0.)
    //p.x += 1.;
    ret.x = rd.x > 0.0 ? ceil(p.x + e) +e: floor(p.x - e) - e;
    ret.y = rd.y > 0.0 ? ceil(p.y + e)  +e : floor(p.y - e) - e;
    ret.z = rd.z > 0.0 ? ceil(p.z + e) + e: floor(p.z - e) - e;
//    ret.x = floor(p.x + sign(rd.x) );
    return ret;
}
float computeoutline(vec3 p, vec3 qu, vec3 n) {
    float ret = 0.;
    float k1 = .5;
    float k2 = .4;

    vec3 op = abs( p - floor(p) - vec3(.5));
    op = smoothstep(vec3(k1), vec3(k2), op );
    op =  abs(1.-op) - .3;
    ret = op.x + op.y+ op.z;
    return  ret ;
}
vec4 rm(vec3 ro, vec3 rd, out float outl, out vec3 n, float vf, out vec3 op) {
    vec4 ret;
    vec3 off = vec3(0.);
    for (int i = 0; i < 331; ++i) {
        vec3 p = ro + off;
        p /= vf;
        vec3 offside = fc(p, rd);
        vec3 qu = offside;
        offside -= p;
        vec3 ff = offside;
        offside /= rd;
        //offside = abs(offside);
        float t = min(offside.x, min(offside.y, offside.z));
        vec3 next = vec3(rd * t);
        vec4 d = map( qu  * vf);
        
            //outl = computeoutline(p, qu, sign(rd) * ff);
        if (d.x < 0.) {
            op = qu*vf;
            outl = computeoutline(p, qu, sign(rd) * ff);
            ret = vec4(length(off  ) , d.yzw);
            n = normalize( sign(rd) * fc(ff, rd)  );
            return ret;
        }

        off += next * vf;
    }
    return vec4(0.);
}

vec3 getnormal(vec3 p) {
    float e = .0001;
    vec3 o = vec3(0., e, -e);
    
    return normalize( vec3 ( map(p + o.zxx).x - map(p + o.yxx).x,
    map(p + o.xzx).x - map(p + o.xyx).x,
    map(p + o.xxz).x - map(p + o.xxy).x
    )
    );
}

void getcam(vec2 uv, out vec3 rd, out vec3 ro){
float tt = fract( time() / 16. );
tt = 0.;
if (tt < .5) {
 ro = vec3(-25., -10.,  -86.4 + t());
 rd = normalize(vec3(uv.x + .15, uv.y + .06, 1.));

} else   {
    float ti = (fract(time() / 16.) - .5) * 2.;
 ro = vec3(0., 4.,  -226.4 + t() + ti * 251.);
 rd = normalize(vec3(uv.x, uv.y + .06, 1.));
}

}
float hash31(vec3 p) {
    return fract( sin(dot(sin(vec3((312.87121) * p )), vec3(31.128271, 77.9511,21.92361))) );
}

float computeEdges(vec4 va, vec4 vb, vec4 vc) {
    return 1.;
}

float computeAO(vec4 va, vec4 vb, vec4 vc) {
   // return va.y;
    vec4 s  = va + vb + vc ;
    
    return (9.-(s.x+s.y+s.z+s.w)) / 9.;
}
void main()
{
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;
       vec3 ro;
    vec3 rd;
    getcam(uv, rd, ro);
    float outl;
    vec3 n;
    vec3 op;
    vec4 r = rm(ro, rd, outl, n, vres, op);
    vec3 p = ro + rd * r.x;
    p = op;
    float id = hash31(floor(p / (vres)));
    vec3 oo = vec3(0., 1., -1.) * vres;
    vec4 va = -vec4( map(p + oo.zxx).x, map( p + oo.yxx).x, 
    map( p + oo.xyx).x, map( p+oo.xzx).x);
    vec4 vb = -vec4( map(p + oo.xxy).x, map( p + oo.xxz).x, 
    map( p + oo.yxy).x, map( p + oo.zxz).x);
    vec4 vc = -vec4( map(p + oo.xxy).x, map( p + oo.zzy).x, 
    map( p + oo.yxx).x, map( p + oo.yzz).x);
    
    va = vec4(greaterThan(  max(vec4(0.), va ), vec4(0.)));
    vb = vec4(greaterThan(  max(vec4(0.), vb ), vec4(0.)));
    vc = vec4(greaterThan(  max(vec4(0.), vc ), vec4(0.)));

float ao = computeAO(va, vb, vc);
    //n = getnormal(p);
    float ndotl = max(.1, dot(n, normalize(vec3(-1., 1., 11.) ) ) );
   // vec3 col = vec3( pow(r.x, 3.)/10000.);
   
     vec3 col = vec3(0., 1., 1.);
   //  outl*=5.;
     if (r.y == 1.) {
         vec3 albedo = mix(vec3(0., 2., 0.), vec3(1.000,.300,0.000) ,
         smoothstep(-.5, .2, rd.y));
           albedo = mix(albedo, vec3(1., 0., 0.), chomp() / 20.);
         col =2.* albedo + albedo * ndotl + outl / 10.;
      // if(fract(.1*time() + rd.x) < .5)
         //col = albedo*outl;
     } if (r.y == 3.) {
         col = vec3(ndotl + outl);
     }
     if (r.y == 4.) {
         col = vec3(ndotl * vec3(1., .3, 0.) * outl);
     }
     if (r.y == 5.) {
     
     float x = noise2(p / 20. + vec3(0., 0., -0.)  * time());
          float y = noise2(p / 15.);
        vec3 albedo = pal( x + time() * .5, vec3(0.5,0.5,.5),vec3(0.5,0.5,0.5),vec3(.5,.5,.5),vec3(0.0,0.33,0.67) );
        vec3 albedo2 = pal( y, vec3(0.5,0.51,0.5),vec3(0.1,0.5,0.2),vec3(.2,1.,.2),vec3(0.0,0.33,0.67) );
      //  albedo = vec3(1., .0, .0);
        //albedo2 = vec3(1., 1., 1.);
          float t = 1./(r.z / 10.);
          outl *= chomp() / 5.;
         //vec3 outl = vec3(.2, .8, .1) * outl * 2.;
//         col = albedo2;
         col = mix(vec3( ndotl * albedo + albedo2 * t), vec3(ndotl) * outl, .2);
//         col = albedo2;
col *=   vec3(.5, 0.0, 0.2) * 4.;
     }
     if (r.y == 6.) {
         col = vec3(outl);
     }
     col = mix(col, vec3(0.0, 1., 1.), ( r.x  - 100.) / 200.);

     if (r.y == wf()) {
         ;//col = outl * vec3(0., 1., 0.);
     }
     if (r.y != 0.)
     col *= .8 +ao / 2.;
     //col += id  / 13.;
    fragColor = vec4(col,1. + 0.000001 * (energy_fast + energy_mid + energy_slow + bpm + intensity + tf + scale + time()));
}