#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D FlowTex;
uniform sampler2D AccumTex;
uniform float flow_gain;
uniform float persistence;
uniform float noise_threshold;
uniform float flow_valid;
uniform float drift;

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution;

    // On the very first frame there is no previous luminance to difference against,
    // and both buffers may still hold whatever the FBO pool handed us. The estimate
    // is meaningless, so emit a clean zero rather than let the accumulator below
    // latch onto it -- max() would hold that garbage for many frames.
    if (flow_valid < .5){
        fragColor = vec4(0.);
        return;
    }

    vec4 f = texture(FlowTex, uv);

    // Semi-Lagrangian backtrace: whatever arrives here was carried in from
    // upstream by the field's own velocity, so read the previous field at where
    // it came from rather than at this pixel. That is what makes a trail keep
    // travelling once the movement that created it has stopped, instead of
    // fading in place. Unconditionally stable at any drift.
    //
    // Clamped rather than wrapped: without this a trail leaving one edge
    // reappears on the opposite side.
    vec2 src = clamp(uv - texture(AccumTex, uv).xy*drift, vec2(0.), vec2(1.));
    vec4 prev = texture(AccumTex, src);

    vec2 flow = f.xy*flow_gain;

    // Soft deadband. A camera pointed at a still scene still produces a low
    // amplitude field everywhere, which would otherwise settle into a permanent haze.
    float mag = length(flow);
    flow = mag < noise_threshold ? vec2(0.) : flow*(1. - noise_threshold/mag);

    float decay = clamp(persistence, 0., .999);
    vec2 faded = prev.xy*decay;

    // Whichever is stronger wins: fresh motion writes in immediately at full
    // amplitude, and what is left behind fades geometrically. Blending instead
    // would smear new movement against the trail it is trying to replace.
    vec2 acc = dot(flow, flow) > dot(faded, faded) ? flow : faded;

    fragColor = vec4(acc, 0., max(f.a, prev.a*decay));
}
