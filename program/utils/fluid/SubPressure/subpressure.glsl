#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D FieldStateSP;
uniform float vort_amount;

#define s(uv, offset) texture(FieldStateSP, uv+offset)
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

    // Substract pressure gradient

    vec2 gradP = vec2(sr.w-sl.w, st.w-sb.w);

    state.xy -= gradP;

    //vorticity 
    float amount = vort_amount;
    float curl = st.x-sb.x + sr.y-sl.y;
    float div = st.y-sb.y + sr.x-sl.x;
    state.z = curl;
    vec2 vorticity = vec2(abs(st.z) - abs(sb.z), abs(sr.z) - abs(sl.z));
    state.xy += amount * 
                    ((length(vorticity) != 0)?
                       normalize(vorticity): vec2(0.))*curl;

    fragColor = state;
}
