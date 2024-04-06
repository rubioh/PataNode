#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D InkState;

#define S(a,b,c) smoothstep(a,b,c)

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;
    vec2 R = iResolution.xy;

    vec3 I = texture(InkState, uv).rgb;
    fragColor = vec4(I, 1.);
    return;
    vec2 dx = vec2(1./R.y, 0.);
    vec3 rd = normalize(vec3(uv, -1));
    float m = 1.;
    float px = pow(length(texture(InkState, uv+dx).rgb), m);
    float py = pow(length(texture(InkState, uv+dx.yx).rgb), m);
    float p = pow(length(I.rgb), m);
    
    px -= p;
    py -= p;
    float m2 = 10.;
    vec3 bumpMap = vec3(px, py, 0.)*m2;

    vec3 lp = vec3(0., 0., -.85);
    vec3 sp = vec3(uv, 0.);
    vec3 ld = (lp-sp);
    ld = ld/max(length(ld), .00001);

    vec3 n = normalize(bumpMap+vec3(0.,0.,-1));
    float spec = pow(max(dot(reflect(-ld, n), -rd), 0.), 2);
    vec3 diff = I*max(dot(n, ld), 0.);
    vec3 fresnel = I*pow(1. + dot(rd, n), 3.);
    
    vec3 col = fresnel*.15 + diff*.8;
    // Output to screen
    fragColor = vec4(col, 1.0);
}
