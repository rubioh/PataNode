#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D FieldState;
uniform sampler2D VelocityState;
uniform float dt;
uniform float advect_amount;
uniform float input_vel_intensity;
uniform float input_vel_intensity_passthrough;
uniform float gate_open;

#define s(uv, offset) texture(FieldState, uv+offset)
#define R iResolution
#define S(a,b,c) smoothstep(a,b,c)

void main(){
    vec2 uv = gl_FragCoord.xy/R;

    vec3 vel_infos = texture(VelocityState, uv).rgb;
    vec2 vel = vel_infos.xy;
    if (gate_open == 1) vel *= input_vel_intensity;
    else vel *= input_vel_intensity_passthrough;

    vec4 state = texture(FieldState, uv);
   
    vec2 tmp = uv+dt*state.xy/R*advect_amount;
    
    vec4 color = texture(FieldState, uv+dt*state.xy/R*advect_amount);
    if (tmp.x<0 || tmp.x>1)
        vel *= 0.;
    if (tmp.y<0 || tmp.y>1)
        vel *= 0.;

    color.xy += vel;

    fragColor.xy = clamp(color.xy, vec2(-10), vec2(10)) * .99;
    fragColor.zw = color.zw;
}
