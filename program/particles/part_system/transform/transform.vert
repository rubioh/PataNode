#version 330 core

in vec4 in_pos;
in vec3 in_col;

out vec4 out_pos;
out vec3 out_col;

uniform float dt;
uniform vec2 gravity;
uniform float part_radius;
uniform float part_size;
uniform sampler2D iChannel0;
uniform float on_kick;
uniform int iFrame;
uniform vec2 iResolution;
uniform sampler2D pos_target;

#define W iResolution.x/iResolution.y/2

float hash(float x){
    return fract(sin(x*174.5783+.742)*1273.489);   
}

float get_radius(int i){    
    float rad = (hash(float(i))*part_radius-part_radius/2) + part_radius;
    return rad*W*.00001 + part_radius*W;
}

vec2 hash22(vec2 p){
    float k1 = dot(vec2(1.4561, 2.45861), p);
    float k2 = dot(vec2(3.4892, 1.5465), p);
    return fract(sin(vec2(k1, k2)*1.156787)*1.35412);
}

vec2 check_boundary(vec2 pos, inout vec2 friction){
    vec2 new_pos = pos;
    friction = vec2(1.);

    float dy = pos.y;//*sign(pos.y);
    float dist = abs(dy);
    float radius = part_size/iResolution.y;
    if (dist > 1.-radius){
        new_pos.y = pos.y - sign(dy)*(radius-(1.-dist));
        friction.y = .7;
        friction.x = .1;
    }

    float dx = pos.x;//*sign(pos.y);
    dist = abs(dx);
    radius = part_size/iResolution.x;
    if (dist > 1.-radius){
        new_pos.x = pos.x - sign(dx)*(radius-(1.-dist));
        friction.x = .7;
        friction.y = .1;
    }
    return new_pos;
}

vec2 getAcceleration(vec2 a, vec2 pos){
    float ID = gl_VertexID;
    vec2 where = vec2(floor(ID/100), mod(ID, 100));
    vec2 target = texelFetch(pos_target, ivec2(where), 0).xy;
    vec2 to_target = -normalize(pos-target)*.02;
    return a + gravity + to_target*.0001;
}

vec2 getVelocity(vec2 pos_last, vec2 pos){
    return (pos - pos_last)/dt;
}

vec2 setVelocity(vec2 pos, vec2 vel){
    return pos - vel*dt;
}

vec2 addVelocity(vec2 pos_last, vec2 vel){
    return pos_last - vel*dt;
}

vec3 get_col(vec2 new_pos){
    vec2 uv = (new_pos+1.)/2.;
    vec3 new_col = texture(iChannel0, uv).rgb;
    new_col = clamp(new_col, vec3(0.), vec3(1.));
    if (on_kick == 1)
        return mix(max(in_col*.8, vec3(.02)), new_col, clamp(length(new_col), 0, 1));
   return in_col*.95 +.05*new_col;
}

void main(){

    vec2 pos = in_pos.xy;
    vec2 pos_last = in_pos.zw;

    if (iFrame < 1){
        vec2 new_pos = hash22(pos+gl_VertexID*.001 + pow(gl_VertexID, .1))*2-1;
        vec2 new_last = new_pos;
        out_pos = vec4(new_pos, new_last);
        out_col = get_col(new_pos);
        return;
    }
    /*
    if (abs(pos.x)>1 || abs(pos.y)>1){
        vec2 new_pos = hash22(pos)*2-1;
        vec2 new_last = new_pos;
        out_pos = vec4(new_pos, new_last);
        out_col = get_col(new_pos);
        return;
    }
    */

    vec2 acceleration = getAcceleration(vec2(0.), pos);
    // Store Old Position
    vec2 new_last = pos;

    // Check Boundary
    vec2 friction = vec2(1.);
    pos = check_boundary(pos, friction);

    // Velocity
    vec2 displacement = pos-pos_last;
    float ld = length(displacement);
    ld = clamp(ld, .0, .015);
    displacement = ((ld >= 0.00001)? normalize(displacement) : vec2(0.))*ld;
    // Verlet Integration
    vec2 new_pos = pos + friction*displacement*.99 + acceleration*(dt*dt);



    out_pos = vec4(new_pos, new_last);
    out_col = get_col(new_pos);
}
