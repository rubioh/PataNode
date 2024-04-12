#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D InkState;
uniform sampler2D FieldState;
uniform sampler2D iChannel0;
uniform float dt;
uniform float advect_amount;
uniform float gate_open;
uniform float decay_rate;
uniform float passthrough;
uniform float iFrame;

#define T(uv, offset) texture(InkState, uv + offset)
#define S(a,b,c) smoothstep(a,b,c)

void main()
{

    vec2 R = iResolution;
    vec2 uv = gl_FragCoord.xy/R;

    vec2 vel = texture(FieldState, uv).xy;

    vec3 tex = texture(iChannel0, uv).xyz;
    tex = clamp(tex, vec3(0.), vec3(1.))*1.;

    if (iFrame <= 0){
        fragColor.rgb = tex;
        return;
    }
    vec3 newink = tex.rgb*( (gate_open == 0.) ?  passthrough : 1.);//*S(.6, 0., length(uv-.5));

    vec2 advection = dt*vel/R*advect_amount;

    vec4 ink = texture(InkState, uv + advection);
    ink.rgb = mix(ink.rgb, newink, min(length(newink), 1.));

    fragColor = ink*decay_rate;
    fragColor.w = 1.;
}
