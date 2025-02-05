#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform float energy;
uniform float energy_fast;
uniform float energy_fast2;
uniform float energy_mid;
uniform float energy_slow;
uniform float bpm;
uniform float onTempo;
uniform float dist;
uniform float onKick;
uniform float energy_fast_cam;

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

float hash31(vec3 p) {
    float h = dot(p,vec3(127.1,311.7, 21.));    
    return fract(sin(h)*43758.5453123);
}

float hash21( vec2 p ) {
    float h = dot(p,vec2(127.1,311.7)); 
    return fract(sin(h)*43758.5453123);
}

vec3 hash13(float n) {
    float n1 = n;
    float n2 = hash11(n);
    float n3 = hash11(n2);
    return vec3(hash11(n1),hash11(n2),hash11(n3));
}

// Fork of "Fractal Flythrough" by Shane. https://shadertoy.com/view/4s3SRN
// 2023-02-13 22:36:13
// Sorry I got rid of the comment because it helps me navigate the code,
// but go see the original from Shane for amazing explaination
// Smooth minimum function. There are countless articles, but IQ explains it best here:
// https://iquilezles.org/articles/smin
float sminP( float a, float b, float s ){

    float h = clamp( 0.5+0.5*(b-a)/s, 0.0, 1.0 );
    return mix( b, a, h ) - s*h*(1.0-h);
}
vec3 pal( in float t, in vec3 a, in vec3 b, in vec3 c, in vec3 d )
{
    return a + b*cos( 6.28318*(c*t+d) );
}

vec3 stripCols(float t, float z) {
    vec3 albedo2 = .2*pal((-t*20.+z) / 10., vec3(0.5,0.5,.5),vec3(0.1,0.5,0.5),vec3(.2,1.,.2),vec3(0.0,0.33,0.67) );
    return albedo2;
    vec3 cols[3];
    cols[0] = vec3(0.506,0.780,0.255) ;
    cols[1] = vec3(.106,0.280,0.255) ;
    cols[2] = vec3(0.906,0.30,1.255) ;
    
    int id = int( floor(mod(t / 12., 3.)) );
    id += int(z / 10.);
    id = id % 3;
    return cols[id];
}

vec2 getPhase() {
//    return vec2( 0., 0. );
    float t = iTime * 2.;
    float i = smoothstep(0.75, 1.28, abs ( mod(t / 16. - t / 8., 2.) - 1.) );
    return vec2( floor( mod(t / 16., 2.) ),  i );
}

const float FAR = 50.0; // Far plane.

float objID = 0.; // Wood = 1., Metal = 2., Gold = 3..
float hash( float n ){ return fract(cos(n)*45758.5453); }

float pulseHalf() {
    return 1.;
}

float pulse() {
    return pow(  ( 1.+ sin( onTempo *1. )/ 2.), 3.) * .25 + .25;
    return pow( ( sin(iTime * 5.) + 1. ) * .5, 2.) * .75 + .25;
}

float pulseFast() {
    return pow( ( sin(iTime * 12.) + 1. ) * .5, 4.) * .75 + .25;
}

float backStars(vec2 uv) {

    uv.y+=cos(uv.x * 1. +0.) / 4.;
    float ret = 0.;
    uv.x -= iTime / 4.;
    
    for (int i = 0; i < 2; ++i) {
        uv *= 3.;
        float rep = .2;

        vec2 m_uv = mod(uv, rep) - rep / 2.;
        vec2 m_id = floor( uv / rep);
        
        float id1 = hash21(m_id / 123.321);
     //   float id2 = hash22(m_id / 123.321); 
        float star = smoothstep(0.02, 0.01, length(m_uv) );
        if (id1 > 0.98)
            ret = star + ret;
    }
    return ret;
}
// Tri-Planar blending function. Based on an old Nvidia writeup:
// GPU Gems 3 - Ryan Geiss: https://developer.nvidia.com/gpugems/GPUGems3/gpugems3_ch01.html
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


float map(in vec3 q){
//    q.x += 5.;
    q.z/=.5;
     if (getPhase().x == 0.)
    q.y+=cos(q.z/10.) * pow(energy_fast_cam,3.)/2.;
    // benef
    if (getPhase().x == 1.) {
        q*= rotateZ(iTime);
        q.xy+=sin(q.z / 8. + sin(iTime / 512.)) * 2.;
      }

   if (length(max(abs(q.x), abs(q.y))) >11. && getPhase().x==0.) {
      //     return 1.;
   }

   if (length(max(abs(q.x), abs(q.y))) <8.) {

    // q*=2.;
      // q.z+=iTime *32.;
   }

    vec3 p = abs(fract(q/4.)*4. - 2.);
    float tube = min(max(p.x, p.y), min(max(p.y, p.z), max(p.x, p.z))) -4./3. - .015;// + .05;
    vec3 qq = abs(q);
    float amp =  2.;// + onTempo/5.;//+ sin(iTime) /2.;
    
    for (int i = 0; i < 3 ; ++i) {
        // Layer two.
        qq *=rotateZ( ( -iTime /8.) * float(getPhase().x == 1.) );
        p = abs(fract(qq)*amp - amp/2.);
        //d = max(d, min(max(p.x, p.y), min(max(p.y, p.z), max(p.x, p.z))) - s/3.);// + .025
        tube = .15*(pulse()-.25)+max(tube, sminP(max(p.x, p.y), sminP(max(p.y, p.z), max(p.x, p.z), .05), .05) - 2./3.);// + .025
        qq/=4.;
        amp *= 1.5;
     }
    float strip = step(p.x, .75)*step(p.y, .75)*step(p.z, .75);
    tube -= (strip)*.025;     

    float repxy = 20.;// - 5.*pulse();
    float s = .2*(pulse());
    float repz = .051;//.2-pulse()/10.;
    vec3 si = sign(q);
    //q *= rotateY(si.x / 2.);
   // q *= rotateX(-si.y/4.);
   q.z/=2.;

   q.y +=mix( 1.5*sin(q.z * 1. + iTime * 16.) * sin(iTime * 4.), abs(fract(q.z * 2. + iTime * 8.) - .5) * 2., pulse() - .25);
  // q.y += ;
   q *= rotateZ(3.1415/4.);
   q.xy +=5.*sign(q.xy);
   vec3 qball = abs(fract(q/( vec3(repxy, repxy, repz) ))*vec3(repxy, repxy, repz) - vec3(repxy/2., repxy/2., repz/2.));

   float d = length(qball) - s;
   // return d;
    objID = strip;

    objID += step(d, tube) * 3.;
    return min(tube, d);
}

float trace(in vec3 ro, in vec3 rd){

    float t = 0., h;
    for(int i = 0; i < 50; i++){
    
        h = map(ro+rd*t);
        // Note the "t*b + a" addition. Basically, we're putting less emphasis on accuracy, as
        // "t" increases. It's a cheap trick that works in most situations... Not all, though.
        if(abs(h)<.001*(t*.25 + 1.) || t>FAR) break; // Alternative: 0.001*max(t*.25, 1.)
        t += h*1.;
        
    }

    return t;
}

vec3 calcNormal(in vec3 p) {
    const vec2 e = vec2(0.005, 0);
    return normalize(vec3(map(p + e.xyy) - map(p - e.xyy), map(p + e.yxy) - map(p - e.yxy), map(p + e.yyx) - map(p - e.yyx)));
}

void main( ){
   
    
    vec2 u = (gl_FragCoord.xy - iResolution.xy*0.5)/iResolution.y;
    
    
    vec3  ro = vec3(0., 0., 1. + dist / 1.3);
    vec3 lk = vec3(0., 0., 2. + dist / 1.3);
    vec3 lp = lk;
    // Using the above to produce the unit ray-direction vector.
    float FOV =6.57 + pulse(); // FOV - Field of view.
    vec3 fwd = normalize(lk-ro);
    vec3 rgt = normalize(vec3(fwd.z, 0, -fwd.x));
    vec3 up = (cross(fwd, rgt));
    
        // Unit direction ray.
    vec3 rd = normalize(fwd + FOV*(u.x*rgt + u.y*up));
    
    
    // Raymarch the scene.
    float t = trace(ro, rd);
    
    // Initialize the scene color.
    vec3 col = vec3(0);
    

    float lum = 0.;
    // Scene hit, so color the pixel. Technically, the object should always be hit, so it's tempting to
    // remove this entire branch... but I'll leave it, for now.
    if(t<FAR){
        
        // This looks a little messy and haphazard, but it's really just some basic lighting, and application
        // of the following material properties: Wood = 1., Metal = 2., Gold = 3..
    
        float ts = 1.;  // Texture scale.
        
        // Global object ID. It needs to be saved just after the raymarching equation, since other "map" calls,
        // like normal calculations will give incorrect results. Found that out the hard way. :)
        float saveObjID = objID; 
        
        
        vec3 pos = ro + rd*t; // Scene postion.
        vec3 nor = calcNormal(pos); // Normal.
        vec3 sNor = nor;

        // Reflected ray. Note that the normal is only half bumped. It's fake, but it helps
        // taking some of the warping effect off of the reflections.
        vec3 ref = reflect(rd, normalize(sNor*.5 + nor*.5)); 
                 
        col = vec3(0.) * /* tex3D(iChannel0, pos*ts, nor)*/ vec3(0.925,0.388,0.067); // Texture pixel at the scene postion.
        
        
        vec3  li = lp - pos; // Point light.
        float lDist = max(length(li), .001); // Surface to light distance.
        float atten = 1./(1.0 + lDist*0.125 + lDist*lDist*.05); // Light attenuation.
        li /= lDist; // Normalizing the point light vector.
        
        float occ = 1.;//calcAO( pos, nor ); // Occlusion.
        
        float dif = clamp(dot(nor, li), 0.0, 1.0); // Diffuse.
        dif = pow(dif, 4.)*2.;
        float spe = pow(max(dot(reflect(-li, nor), -rd), 0.), 8.); // Object specular.
        float spe2 = spe*spe; // Global specular.
        
        float refl = .35; // Reflection coefficient. Different for different materials.
        // Reflection color. Mostly fake.
        // Cheap reflection: Not entirely accurate, but the reflections are pretty subtle, so not much 
        // effort is being put in.
        float rt = 0.;//refTrace(pos + ref*0.1, ref); // Raymarch from "sp" in the reflected direction.
        float rSaveObjID = objID; // IDs change with reflection. Learned that the hard way. :)
        vec3 rsp = pos + ref*rt; // Reflected surface hit point.
        vec3 rsn = calcNormal(rsp); // Normal at the reflected surface. Too costly to bump reflections.
        vec3 rCol = vec3(1.);//tex3D(iChannel0, rsp*ts, rsn); // Texel at "rsp."
        vec3 rLi = lp-rsp;
        float rlDist = max(length(rLi), 0.001);
        rLi /= rlDist;
        float rDiff = max(dot(rsn, rLi), 0.); // Diffuse light at "rsp."
        rDiff = pow(rDiff, 4.)*2.;
        float rAtten = 1./(1. + rlDist*0.125 + rlDist*rlDist*.05);
        
        float f =  pow( energy_fast / 2., 5.) / .5;
        if(rSaveObjID <  1.){
         //   lum = 2.;
         lum = 0.;
            col *= 1.*vec3(0.549,0.475,0.557);
        } else if (rSaveObjID < 1.5){
            col = stripCols(iTime, pos.z) * f;
            lum = 15.*f;
        } else {
            col = vec3(0.169,0.745,0.867);
            lum = 100. * (pulse()-.25) * (1.+sin(pos.z * 5.) / 2.);
        }
        
        col += 1.3*vec3(0.269,0.345,0.767) * ( pulse() - .25);
        col +=1.1*stripCols(iTime, pos.z) * ( f - .25);
        rCol *= (rDiff + .35)*rAtten; // Reflected color. Not accurate, but close enough.         
        
        if(length(pos.xy) > 20.)
            col *=2.;
        // Combining everything together to produce the scene color.
        col = col*(dif + .35  + vec3(.35, .45, .5)*spe*2.) + vec3(.7, .9, 1)*spe2 * 2. + rCol*refl;
        col *= occ* ( atten); // Applying occlusion.
        col += stripCols(iTime, pos.z) * (col + abs(nor.x) / 5.);
        
    }    else{ col=vec3( backStars(u * 4.)); lum = col.r*20.; if(energy_fast==123.12)col = vec3(energy_fast+energy_fast2 + energy_slow+energy+energy_mid+onTempo+onKick);}
    fragColor = vec4(pow( (max(col * 3., 0.)), vec3( 1.2 ) ), lum /2000.);
}