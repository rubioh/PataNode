#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform sampler2D iChannel0;
uniform float energy;
uniform float t;
uniform float hscale;

float hash21(vec2 p){
    vec2 a = vec2(17.456, 321.746);
    vec2 b = vec2(121.753, 364.789);
    vec2 c = vec2(1247.326, 2453.689);
    return fract(sin(vec2(dot(a,p), dot(b,p)))*c).x;
}

vec2 hash22(vec2 p){
    vec2 a = vec2(17.456, 321.746);
    vec2 b = vec2(121.753, 364.789);
    vec2 c = vec2(1247.326, 2453.689);
    return fract(sin(vec2(dot(a,p), dot(b,p)))*c);
}

float noise(vec2 p){
    vec2 i = floor(p);
    vec2 f = fract(p);

    // Four corners in 2D of a tile
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));

    // Smooth Interpolation

    // Cubic Hermine Curve.  Same as SmoothStep()
    vec2 u = f*f*(3.0-2.0*f);
    // u = smoothstep(0.,1.,f);

    // Mix 4 coorners percentages
    return mix(a, b, u.x) +
            (c - a)* u.y * (1.0 - u.x) +
            (d - b) * u.x * u.y;
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    float vx = (pow(noise(vec2(uv.y, uv.y)*(40.+20.*cos(t*.1*.1))*hscale + noise(vec2(t, -t))*4.), 4.)) *
        (noise(vec2(uv.y, 0.)*15.)*2.-1.) * 2.;

    float vy = (pow(noise(vec2(uv.x, uv.x)*(40.+20*cos(t*.1)) + noise(vec2(t, -t)*.05)*8.), 4.)) *
        (noise(vec2(uv.x, 0.)*15.)*2.-1.) * 2.;
    vy = .0;

    vec3 col = texture(iChannel0, uv + vec2(vx, vy)*.1*energy).rgb;
    vec3 col1 = texture(iChannel0, uv + vec2(vx, vy)*.15*energy).rgb;
    vec3 col2 = texture(iChannel0, uv + vec2(vx, vy)*.2*energy).rgb;

    col = vec3(col.r, col1.g, col2.b);

    //col = mix(col, (1.-col)*length(col)/sqrt(3.), vy*vx*energy);

    fragColor = vec4(col,1.0);

}
