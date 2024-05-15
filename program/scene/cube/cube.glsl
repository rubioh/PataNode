#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform float energy_fast;
uniform float energy_mid;
uniform float bpm;
uniform float sens;
uniform float intensity;
uniform float vitesse;
uniform float trigger;
uniform float deep;
uniform float face;
uniform float go_rot;
uniform float side_col;
uniform vec3 color;
uniform float N_sq;
uniform float zoom_factor;
uniform float show_bulb;

const int MAX_MARCHING_STEPS = 	100;
const float MIN_DIST = 1.0;
const float MAX_DIST = 100.0;
const float PRECISION = 0.0001;


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

mat3 rotate(float t){

    mat3 z = rotateZ(t);
    mat3 x = rotateX(t);
    mat3 y = rotateY(t);
    
    return x*y*z;
}
mat3 identity(){
    return mat3(1., 0., 0., 0., 1., 0., 0., 0., 1.);
}
float sdBox( vec3 p, vec3 b )
{
  vec3 q = abs(p) - b;
  return length(max(q,0.0)) + min(max(q.x,max(q.y,q.z)),0.0);
}
float sdSphere( vec3 p, float r)
{
  return length(p)-r;
}

vec3 opRepLim( in vec3 p, in float c, in float N)
{
    vec3 l = vec3(N);
    vec3 q = p-c*clamp(floor(p/c+.5),-l,l);
    q.x = p.x;
    return q;
}

vec3 opTx(vec3 p){
   
    mat3 rot = deep<3? rotate(iTime/8): rotate(iTime/4.);
    p = rot*p;
    return p * zoom_factor;
}

vec4 SDF (vec3 p)
{
    float d = 1e10;
    
    
    p = opTx(p);
    vec3 b = vec3(.5, .5, .5);

    vec3 idx = floor(p/(1.+energy_fast)+.5);

    mat3 rotZ = rotateZ(go_rot * (int(face == 1.)-int(face == -1)));

    mat3 rotX = rotateX(go_rot * (int(face == 2.)-int(face == -2)));

    mat3 rotY = rotateY(go_rot * (int(face == 3.)-int(face == -3)));


    vec3 p2 = ((idx.x == face/2) ? 
                    opRepLim(rotX*p, 1.+energy_fast, N_sq) : 
                        ((idx.z == face) ? 
                            opRepLim(rotZ*p, 1.+energy_fast, N_sq) : 
                            (idx.y == face/3) ?
                                opRepLim(rotY*p, 1.+energy_fast, N_sq) : 
                                opRepLim(p, 1.+energy_fast, N_sq)));
    vec3 square_color = color;
    if (side_col == 1.){
        square_color = ((idx.x == face/2) ? 
                        color: 
                            ((idx.z == face) ? 
                                color : 
                                ((idx.y == face/3) ?
                                    color : 
                                    color - .75)));
    }
    d = (p==p2) ? d : sdBox(p2, b*(1.+deep*energy_fast/10.));
    if (show_bulb == 1.){
        float displacement = sin(p.z*5.-iTime/2.+2.)*sin(p.x*5.-iTime/4+1.)*sin(p.y*5.-iTime+0.)*.1*(energy_mid+deep/2.);
        float dt = (p==p2) ? sdSphere(p/1.5, .4)+displacement+1000 : sdBox(p2, b*(1.+deep*energy_fast/10.));
        vec3 col = (p==p2) ? vec3(1., .58, .29) : square_color*.95 ;
        d = min(d, dt);
        return vec4(d, col);
    }
    else return vec4(d, square_color);
}


vec3 calcNormal(vec3 p) {
    vec2 e = vec2(1.0, -1.0) * 0.002; // epsilon
    float r = 1.; // radius of sphere
    return normalize(
      e.xyy * SDF(p + e.xyy).x +
      e.yyx * SDF(p + e.yyx).x +
      e.yxy * SDF(p + e.yxy).x +
      e.xxx * SDF(p + e.xxx).x);
}

vec4 rayMarch(vec3 ro, vec3 rd, float start, float end) {
  float depth = start;
  vec3 col;
  for (int i = 0; i < MAX_MARCHING_STEPS; i++) {
    vec3 p = ro + depth * rd;
    vec4 d = SDF(p);
     depth += d.x*.5;
    if (abs(d.x) < PRECISION || depth > end){
        col = d.yzw;
        break;}
  }
  return vec4(depth, col);
}

vec3 phong(vec3 lightDir, vec3 normal, vec3 rd, vec3 col) {
  // ambient
  vec3 ambient = col*(.5+.5*normal.y);

  // diffuse
  float dotLN = clamp(dot(lightDir, normal), 0., 1.);
  vec3 diffuse = col * dotLN;

  // specular
  float dotRV = clamp(dot(reflect(lightDir, normal), -rd), 0., 1.);
  vec3 specular = 3.*col * pow(dotRV, 5.);

  
  return (col.x==1.) ? (ambient + diffuse + specular) : (ambient + .2*diffuse + .2*specular);
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;
    vec3 col;
    vec3 color = vec3(.8,.1,.1);
    vec3 normal;

    mat3 rot = rotate(iTime/32.+2.);

    vec3 ro = vec3(0, 0, 8-1.5*deep); // ray origin that represents camera position
    vec3 rd = normalize(vec3(uv, -1)); // ray direction

    vec4 d = rayMarch(ro, rd, MIN_DIST, MAX_DIST); // distance to sphere
    vec3 backgroundColor = vec3(.0);
    if (d.x > MAX_DIST) {
        col = backgroundColor; // ray didn't hit anything
        } else {

        vec3 p = ro + rd * d.x; // point on sphere we discovered from ray marching
        normal = calcNormal(p);
        vec3 lightPosition = rot*vec3(1, 1, 2);
        vec3 lightDirection = normalize(lightPosition - p);
        float lint = 1.2;
        col = lint*phong(lightDirection, normal, rd, d.yzw);
    }
    //col = vec3(pattern_border(uv*2.));
    // Output to screen
    fragColor = vec4(clamp(col, vec3(0.), vec3(1.)), 1.0);
    }
