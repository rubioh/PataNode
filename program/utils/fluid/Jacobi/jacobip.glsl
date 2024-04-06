#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D FieldState;

#define s(uv, offset) texture(FieldState, uv+offset)
#define R iResolution

void main(){
    
    vec2 uv = gl_FragCoord.xy/R;

    vec4 state = s(uv, vec2(0.));

    vec4 st = s(uv, vec2(0., 1./R.y));
    vec4 sb = s(uv, vec2(0., -1./R.y));
    vec4 sr = s(uv, vec2(1./R.x, 0.));
    vec4 sl = s(uv, vec2(-1./R.x, 0.));

    // Jacobi iteration
    float div = (sr.x-sl.x  +  st.y-sb.y);
    float np = (st.w + sb.w + sr.w + sl.w - div)/4.;

    state.w = np;
    fragColor = state;
}
