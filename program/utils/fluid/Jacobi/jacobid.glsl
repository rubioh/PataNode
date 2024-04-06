#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D FieldState;
uniform float dt;
uniform float kappa;

#define s(uv, offset) texture(FieldState, uv+offset)
#define R iResolution

vec4 advect(vec2 uv, vec2 advection, float A){
    return s(uv, advection*A);
}

void main(){
    
    vec2 uv = gl_FragCoord.xy/R;

    vec4 state = s(uv, vec2(0.));

    vec4 st = s(uv, vec2(0., 1./R.y));
    vec4 sb = s(uv, vec2(0., -1./R.y));
    vec4 sr = s(uv, vec2(1./R.x, 0.));
    vec4 sl = s(uv, vec2(-1./R.x, 0.));

    // Jacobi iteration

    state.xyz = (state.xyz + dt*kappa*(st.xyz+sb.xyz+sr.xyz+sl.xyz))/(1.+4.*dt*kappa);
    fragColor = state;
}
