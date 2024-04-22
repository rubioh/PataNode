#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform float energy_fast;
uniform float energy_slow;
uniform float decaying_kick;
uniform float move_x;
uniform float move_z;
uniform float on_tempo;
uniform float on_tempo2;
uniform float on_tempo4;
uniform vec3 l;
uniform float mode;
uniform vec3 color;
uniform float angle_t;
uniform float y_t;
uniform float trigger;
uniform float rot_final;
uniform float min_dist;
uniform float on_chill;

#define AA 0
#define PI 3.14159
#define TAU 6.28318
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


float sdCapsule( vec3 p, vec3 a, vec3 b, float r )
{
  vec3 pa = p - a, ba = b - a;
  float h = clamp( dot(pa,ba)/dot(ba,ba), 0.0, 1.0 );
  return length( pa - ba*h ) - r;
}

float opSmoothSubtraction( float d1, float d2, float k ) {
    float h = clamp( 0.5 - 0.5*(d2+d1)/k, 0.0, 1.0 );
    return mix( d2, -d1, h ) + k*h*(1.0-h); }

vec2 hash22(vec2 p)
{
    p *= 100.;
	vec3 p3 = fract(vec3(p.xyx) * vec3(.1031, .1030, .0973));
    p3 += dot(p3, p3.yzx+33.33);
    return fract(sin(p3.xy+p3.yz)*p3.zy);
}

vec3 hash33(vec3 p)
{
    p *= 100.;
	vec3 p3 = fract(vec3(p.xyz) * vec3(.1031, .1030, .0973));
    p3 += dot(p3, p3.yzx+33.33);
    return fract(sin(p3.xyz+p3.yzx)*p3.zxy);
}

float sdSphere(vec3 p, float r, vec3 offset)
{
  return length(p - offset) - r;
}

float opSmoothUnion( float d1, float d2, float k ) {
    float h = clamp( 0.5 + 0.5*(d2-d1)/k, 0.0, 1.0 );
    return mix( d2, d1, h ) - k*h*(1.0-h); }


float sdTorus( vec3 p, vec2 t )
{
  vec2 q = vec2(length(p.xz)-t.x,p.y);
  return length(q)-t.y;
}

float sdPlane( vec3 p, vec3 n )
{
  // n must be normalized
  return dot(p,n) + 1.;
}

float sdRoundBox( vec3 p, vec3 b, float r)
{
  vec3 q = abs(p) - b;
  return length(max(q,0.0)) + min(max(q.x,max(q.y,q.z)),0.0) - r;
}

float sdOctahedron( vec3 p, float s)
{
  p = abs(p);
  float m = p.x+p.y+p.z-s;
  vec3 q;
       if( 3.0*p.x < m ) q = p.xyz;
  else if( 3.0*p.y < m ) q = p.yzx;
  else if( 3.0*p.z < m ) q = p.zxy;
  else return m*0.57735027;
    
  float k = clamp(0.5*(q.z-q.y+s),0.0,s); 
  return length(vec3(q.x,q.y-s+k,q.z-k)); 
}

float sdEllipsoid( vec3 p, vec3 r )
{
  float k0 = length(p/r);
  float k1 = length(p/(r*r));
  return k0*(k0-1.0)/k1;
}

float sdRoundCone( vec3 p, float r1, float r2, float h )
{
  // sampling independent computations (only depend on shape)
  float b = (r1-r2)/h;
  float a = sqrt(1.0-b*b);

  // sampling dependant computations
  vec2 q = vec2( length(p.xz), p.y );
  float k = dot(q,vec2(-b,a));
  if( k<0.0 ) return length(q) - r1;
  if( k>a*h ) return length(q-vec2(0.0,h)) - r2;
  return dot(q, vec2(a,b) ) - r1;
}


float Tux(vec3 p, out vec3 col, out float obj, vec3 idx){
    
    float d = 1e10;
    vec3 h = hash33(idx)*2;
    h = vec3(idx.x+idx.y+idx.z);

    if (trigger==1.){
        p.y += y_t;
        mat3 rott = rotateY(angle_t);
        p *= rott;
    }
    else{
        mat3 rott = rotateY(rot_final);
        p*= rott;
    }

    p.y -= sin(decaying_kick)*.2;
    
    // CORE
    vec3 tmp = vec3(0.,cos(on_tempo2+h.y)*.05, 0.05-.03*cos(on_tempo2+h.y));
    vec3 tmp2 = vec3(.5*sin(on_tempo+h.x), .5*cos(on_tempo+h.x), 0.)*.3*energy_slow;
    p += tmp;
    vec3 b = vec3(.25,.8,.3);
    vec3 pt = p;
    pt.y -= .2;
    float d2 = min(d, sdRoundBox(pt, b, .4));
    if (d2<d){
        d = d2;
        col = vec3(.2);
        obj = 1.;
    }
     
    // HEAD
    pt = p;
    pt.y += .1;
    pt *= 1.1;
    d2 = sdSphere(pt, 1., vec3(0.));
    if (d2<d){
        col = mix(col, vec3(.8), smoothstep(0. ,0.01, abs(d2-d)-.02));
        obj = smoothstep(0. ,0.01, abs(d2-d)-.03);
    }
    d = opSmoothUnion(d, d2, .5);
    

    pt = p+tmp2;
    pt.y -= 1.1;
    pt *= 2.;
    d2 = sdSphere(pt, 1.3, vec3(0.));   
    if (d2<d){
        col = vec3(.2);
    }
    d = opSmoothUnion(d, d2, .5);

    // NOSE
    pt = p+tmp2;
    pt += vec3(0.,-.7, -.5);
    pt *= 2.;
    d2 = sdOctahedron(pt, 1.);
    if (d2<d){
        col = mix(col, vec3(.7, .7, 0.), smoothstep(0. ,0.01, abs(d2-d)-.02));
        obj = smoothstep(0. ,0.01, abs(d2-d)-.03);
    }
    d = opSmoothUnion(d, d2, .05);
    
    
    
    // EYES
    pt = p+tmp2;
    pt.x = abs(pt.x);
    pt += vec3(-.35, -1., -.55);
    pt *= 3.5;
    d2 = sdSphere(pt, 1., vec3(0.));   
    if (d2<d){
        col = mix(col, vec3(1.), smoothstep(0. ,0.01, abs(d2-d)-.02));
        obj = smoothstep(0. ,0.01, abs(d2-d)-.03);
    }
    d = opSmoothUnion(d, d2, .05);
    
    pt = p+tmp2;
    pt.x = abs(pt.x);
    pt += vec3(-.35, -1., -.7);
    pt *= 5.5;
    d2 = sdSphere(pt, .5+energy_fast/2., vec3(0.));   
    if (d2<d){
        col = mix(col, vec3(0.), smoothstep(0. ,0.01, abs(d2-d)-.02));
        obj = smoothstep(0. ,0.01, abs(d2-d)-.03);
    }
    d = opSmoothUnion(d, d2, .05);
  
  
    // NAGEOIRE
    pt = p;
    pt.x = -abs(pt.x);
    pt.y -= .3;
    mat3 rot = rotateX(.25+sign(p.x)*.7*cos(on_tempo2+h.z)*(1.-on_chill));
    pt *= rot;
    pt.y += .3;
    pt += vec3(1., 0., 0.);
    rot = rotateZ(-.5);
    pt = rot*pt;
    vec3 r = vec3(1.,2.,1.)/3.;
    d2 = sdEllipsoid(pt, r);   
    if (d2<d){
        col = mix(col, vec3(.1), smoothstep(0. ,0.01, abs(d2-d)-.02));
        obj = smoothstep(0. ,0.01, abs(d2-d)-.03);
    }
    d = opSmoothUnion(d, d2, .01);
    
    
    // PALME
    pt = p;
    pt.x = abs(pt.x);
    pt += vec3(-.4, 1., -.3);
    pt *= 3.5;
    rot = rotateX(.3+sign(p.x)*.5*sin(on_tempo4*(1.-on_chill)+h.z));
    pt *= rot;
    r = vec3(1.3,1.,2.);
    d2 = sdEllipsoid(pt, r);
    if (d2<d){
        col = mix(col, vec3(.7, .7, 0.), smoothstep(0. ,0.01, abs(d2-d)-.02));
        obj = smoothstep(0. ,0.01, abs(d2-d)-.03);
    }
    d = opSmoothUnion(d, d2, .05);

    // Queue
    pt = p;
    pt += vec3(0., .9, 1.1);
    pt.z -= .9;
    rot = rotateY(.3*sin(on_tempo4+h.z));
    pt *= rot;
    pt.z += .9;    
    
    rot = rotateX(-PI/2.+.7);
    pt *= rot;
    d2 = sdRoundCone(pt, .2, .5, .7);
    if (d2<d){
        col = mix(col, vec3(.1), smoothstep(0. ,0.01, abs(d2-d)-.02));
        obj = smoothstep(0. ,0.01, abs(d2-d)-.03);

    }
    d = min(d, d2);

    return d;
}


float map(vec3 p, out vec3 col, out float obj){
    
    float d = 1e10;
    
    p.xz -= vec2(move_x, move_z);

    vec3 n = normalize(vec3(0.,1.,0.));
    //d = min(d, sdPlane(p, n));
    vec3 c = vec3(3.,3.,3.)*2.;
    vec3 q = mod(p-.5*c, c)-.5*c;

    vec3 idx = floor((p-.5*c)/c);

    vec3 q2 = p-c*clamp(floor(p/c+.5), -l, l);

    d = min(d, Tux(mix(q2, q, mode), col, obj, idx));
    
    
    return d;
}

float rayMarch(vec3 ro, vec3 rd, out vec3 col, out float L, out float obj) {
  float id = 0.;
  float depth2 = 1e10;
  float MAX_DIST = 10.;
    int MAX_MARCHING_STEPS = 80;
    float MIN_DIST = min_dist;
    float PRECISION = 0.0001;
  float depth = MIN_DIST;
  for (int i = 0; i < MAX_MARCHING_STEPS; i++) {
    vec3 p = ro + depth * rd;
    float d = map(p, col, obj);
    depth += d;
    if (d < PRECISION){
        depth2 = depth;
        L = 1.;
        break;
        }
    if(d < PRECISION*5.){
        if (id != 1.){
            col *= 0.;
            depth2 = depth;
            L *= 0.;
            
        }
      }
    if (d>MAX_DIST) break;
    }
  return depth2;
}

vec3 calcNormal(vec3 p) {
    vec2 e = vec2(1.0, -1.0) * 0.005; // epsilon
    float r = 1.; // radius of sphere
    vec3 c;
    float obj;
    return normalize(
      e.xyy * map(p + e.xyy, c, obj) +
      e.yyx * map(p + e.yyx, c, obj) +
      e.yxy * map(p + e.yxy, c, obj) +
      e.xxx * map(p + e.xxx, c, obj));
}

mat2 rot(float a)
{
    float s = sin(a);
    float c = cos(a);
    return mat2(c, -s, s, c);
}


mat3 camera(vec3 cameraPos, vec3 lookAtPoint) {
	vec3 cd = normalize(lookAtPoint - cameraPos); // camera direction
	vec3 cr = normalize(cross(vec3(0, 1, 0), cd)); // camera right
	vec3 cu = normalize(cross(cd, cr)); // camera up
	
	return mat3(-cr, cu, -cd);
}

vec3 phong2(vec3 lightDir, vec3 normal, vec3 rd, vec3 col) {
  // ambient
  //
  vec3 ambient = col*(.5);

  // diffuse
  float dotLN = smoothstep(.45, .5, dot(lightDir, normal))/4.;
  vec3 diffuse = col * dotLN;

  // specular
  float dotRV = smoothstep(.85, .9, (dot(reflect(lightDir, normal), -rd)));
  vec3 specular = 2.*col * pow(dotRV, 5.);

  return ambient + diffuse; + specular;
}

vec3 phong(vec3 lightDir, vec3 normal, vec3 rd, vec3 col) {
  // ambient
  float N = 2.;
  vec3 ambient = floor(col*N*.5)/N+.01;

  // diffuse
  float dotLN = floor(clamp(dot(lightDir, normal), 0., 1.)*N)/N;
  vec3 diffuse = col * dotLN * color;

  // specular
  float dotRV = floor(clamp(dot(reflect(lightDir, normal), -rd), 0., 1.)*N)/N;
  vec3 specular = 1.*col * pow(dotRV, 5.) * color;

  return 2.*(ambient + diffuse) + specular*.1;
}

void main()
{
  vec2 uv = (gl_FragCoord.xy-.5*iResolution.xy)/iResolution.y;
  vec3 backgroundColor = vec3(0.1, .1, .1)*.0;
  vec3 col = vec3(0);
  vec3 col_tot = vec3(0.);
  vec3 ro = vec3(4, 4, 4);
  vec2 m = vec2(.61+.1*cos(iTime/512)*mode, .7+.7*sin(iTime/512)*mode);
  
  vec3 lookat = vec3(0,0,0);// ray origin that represents camera position
  ro.yz = ro.yz * 1. * rot(mix(PI/2., 0., m.y));
  ro.xz = ro.xz * rot(mix(-PI, PI, m.x)) + vec2(lookat.x, lookat.z); // remap mouseUV.x to <-pi, pi> range  
  
  vec3 rd = camera(ro, lookat)*normalize(vec3(uv, -1)); // ray direction
  
  float w;
  float obj = 1.;
  for (int i = 0; i<AA+1; i++){
      for (int j = 0; j<AA+1; j++){
          
          vec3 rd2 = rd + vec3(float(i), float(j), 0.)*.001;
          float L = 1.;
          float d = rayMarch(ro, rd2, col, L, obj); // distance to sphere

          if (d > 1000) {
            col_tot += backgroundColor/float(2*(AA+1)); // ray didn't hit anything
          } else {
            vec3 p = ro + rd * d; // point on sphere we discovered from ray marching
            vec3 normal = calcNormal(p);
            vec3 lightPosition = vec3(1, 1, 2);
            lightPosition = 5.*vec3(cos(iTime/128), sin(iTime/128), cos(iTime/128))*mode+4.;
            vec3 lightDirection = normalize(lightPosition - p);
            float lint = 1.2;
            
            // Multiply the diffuse reflection value by an orange color and add a bit
            // of the background color to the sphere to blend it more with the background.
            if (L != 0.) col_tot += obj*lint*phong(lightDirection, normal, rd, col)/float((AA+1));
            else col_tot *= 0.;
          }
    }
  }  
  col = col_tot;
  fragColor = vec4(col, 1.0);
}

