#version 330

in vec4 in_pos;
in vec4 prev_pos;

uniform float N_part;
uniform float iTime;
uniform float dt;
uniform float iFrame;
uniform float energy_slow;
uniform float decay_kick;
uniform float energy_fast;
uniform float next;
uniform float modNext;
uniform float mod_fract;
uniform float mode_chill;

out vec4 out_pos;
out vec4 out_prev;

float hash11(float x){
    return fract(cos(x/100. * 123.567)*178.326);
}

vec3 get_sphere(float ID){
    vec2 p = vec2(0.);

    float phi = (sqrt(5)+1)/2 - 1.;
    float ga = phi*2*3.14159;
    p.x = ga*ID;
    p.x /= 2*3.14159;
    p.x = fract(p.x)*2*3.14159;
    p.y = asin(-1 + 2 * ID/N_part);
    
    vec3 res = vec3(0.);
    float rad = 1;
    float rxz = rad*cos(p.y);
    res.x = rxz * cos(p.x);
    res.y = rad * sin(p.y);
    res.z = rxz * sin(p.x);
    return res;
}


void main() {

    vec3 pos = in_pos.xyz;
    vec3 prev = prev_pos.xyz;

    if (iFrame <= 1){
        vec3 p = get_sphere(gl_VertexID)*4.;
        out_pos = vec4(p, 1.);
        out_prev = vec4(p, 1.);
        return;
    }

    vec3 displacement = pos - prev;
    float ld = length(displacement);
    ld = clamp(ld, .0, .3);
    displacement = ((ld >= .000001)? normalize(displacement) : vec3(0.))*ld;

    float ID = mod(gl_VertexID + (mod_fract)*floor(next), N_part);
    //float ID = gl_VertexID + N_part*.0000001*floor(next);
    vec3 acceleration = (get_sphere(ID)*(8.+energy_slow*1. + energy_fast*2.) - pos);
    vec3 friction = vec3(1.);

    float t = iTime/1000.;
    vec3 new_pos = pos 
            + friction*displacement*(.4-.4*cos(t)) 
            + acceleration*(dt*(.1 +.05*cos(t)));
    
    float goID = mod(gl_VertexID, modNext);
    
    float vel_int = 0;
    if (mode_chill == 0){
        vel_int = (float(goID == .0)*2000.)*.1*pow(decay_kick, 1.);
        vel_int -= step(displacement.y+.05, .0)*displacement.y*4.*pow(decay_kick, .5)*10.;
        vel_int = vel_int * .3 + in_pos.w * .7;
    }
    else{
        vel_int += 1 * step(.99, hash11(gl_VertexID+iTime));
        vel_int = vel_int * .5 + in_pos.w * .5;
    }
    out_pos = vec4(new_pos, vel_int);
    out_prev = in_pos;
}
