#version 330 core
layout (location=0) out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float energy_fast;
uniform float energy_mid;
uniform float energy_slow;
uniform float bpm;
uniform float intensity;
uniform float tf;
uniform float scale;
uniform vec3 l1;
uniform vec3 l2;
uniform vec3 l3;
uniform vec3 l4;
uniform vec3 l5;
uniform vec3 l6;
uniform float strobe1;
uniform float strobe2;
uniform float strobe3;
uniform float strobe4;
uniform float strobe5;
uniform float strobe6;


void main()
{
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;
    vec3 col = l1;
    if (uv.x < 0.) {
        if (uv.y > .33) {
            col = l1;
        } else if (uv.y > -0.33) {
            col = l2;
        } else {
            col = l3;
        }
    } else {
        if (uv.y > .33) {
            col = l4;
        } else if (uv.y > -0.33) {
            col = l5;
        } else {
            col = l6;
        }
    } 

    fragColor = vec4(col, col.x + 1. + 0.1 * (energy_fast + energy_mid + energy_slow + bpm + intensity + tf + scale + iTime, strobe1 + strobe2+strobe3 + strobe4+strobe5+strobe6));
}