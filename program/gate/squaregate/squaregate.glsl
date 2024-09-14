#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform float square_size;
uniform float energy;
uniform float N_SQUARE;
uniform float border_size;
uniform float which;

float hash(float t){
    return fract(sin(t)*17558.246);
}

float sdBox( in vec2 p, in vec2 b )
{
    vec2 d = abs(p)-b;
    return length(max(d,0.0)) + min(max(d.x,d.y),0.0);
}

vec2 square(vec2 uv){
    float d = 10.;
    for (float i=0; i<N_SQUARE; i++){
        float t = iTime*(.5+hash(float(i)*15.5456+11.3))*1. + 100. * float(i)*.094;
        float tidx = floor(t/2.)*2.;
        float tmove = (tidx < 1. ) ? t : tidx;
        float tsize = (tidx < 1. ) ? t : tidx;
        vec2 offset = vec2(hash(tmove*3.53), hash(tmove*2.51))*3.-1.5;
        float H = hash(tsize) + .2;
        vec2 size = H * vec2(1., (.25 + .75*hash(tsize*1.789)))* square_size *  (.5-.5*cos(fract(t/2.)*2.*3.14159));
        if (hash(tsize*17.267)>.5) size.xy = size.yx;
        d = min(d, sdBox(uv-offset, size));
    }
    float border = smoothstep(0./iResolution.y, 2./iResolution.y, abs(d)-.0005*border_size);
    return vec2(smoothstep(1./iResolution.y, .0, d), border);
}


void main()
{
    vec2 uv = (2.*gl_FragCoord.xy - iResolution.xy)/iResolution.y;
    vec2 UV = gl_FragCoord.xy/iResolution.xy;

    vec4 col = vec4(0.);
    vec2 S = square(uv);
    
    if (which == 0) col = mix(texture(iChannel0, UV), texture(iChannel1, UV)*clamp(energy, .0, 1.), S.x);
    else col = mix(texture(iChannel1, UV), texture(iChannel0, UV)*clamp(energy, .0, 1.), S.x);
    col = mix(col, vec4(1.), 1.-S.y);

    fragColor = col;
}
