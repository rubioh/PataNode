#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float smooth_low;
uniform float mode;
uniform float t;
uniform float t_angle;
#define R iResolution
float mask(vec2 uv){
    return step(0, uv.x)*step(uv.x, R.x)*step(0, uv.y)*step(uv.y, R.y);
}

mat2 rot(float angle){
    return mat2( cos(angle), sin(angle), -sin(angle), cos(angle));
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/R;
    
    uv.x = abs(uv.x-.5)+.5 - smooth_low*.01 - (.5+.5*cos(t/27.))*.2;

    if (mode >= 1){
        uv.y = abs(uv.y-.5)+.5 - smooth_low*.01 - (.5+.5*cos(t/37.))*.3;
    }
    
    vec2 st = uv;

        st -= .5;
        st *= R;
        st *= rot(t_angle/40.);
        st /= R;
        st *= 1.3;
        st += .5;

    if (st.x>1) st.x = (1-mod(st.x, 1.));
    if (st.y>1) st.y = (1-mod(st.y, 1.));
    if (st.x<0) st.x = (1-mod(st.x, 1.));
    if (st.y<0) st.y = (1-mod(st.y, 1.));

    vec3 col = texture(iChannel0, st).rgb;
    fragColor = vec4(col,1.0);

}
