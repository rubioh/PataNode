#version 330
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform sampler2D Prev;
uniform sampler2D Alpha;
uniform float decaying_kick;
uniform float mode_chill;
uniform float energy;
uniform float energy_fast;
uniform float energy_mid;
uniform float energy_slow;
uniform float bpm;
uniform float intensity;
uniform float vitesse;
uniform float trigger;
uniform vec3 np_col;

void main()
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;

    vec4 col_now = texture(iChannel0, uv).rgba;
    vec4 col_prev = texture(Prev, uv).rgba;
    float alpha = texture(Alpha, uv).r;

    vec4 col = vec4(0.);

    col.a = alpha*(1.+2.*pow(decaying_kick, .5)+mode_chill*15.);

    col.rgb = col_now.rgb*.8+col_prev.rgb*.2;

    fragColor = vec4(col.rgb, col.a);

}
