#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;

#define R iResolution

#define T(uv, lvl) 10.*pow(dot(texture(iChannel0, uv).rgb, vec3(.299, .587, .114)), lvl)

vec3 calcNormal(vec2 uv){
    float lvl = 1.;
    vec2 e = vec2(1.,-1.)*.0001;
    float orig = T(uv, lvl);
    return normalize(vec3(
        T(uv - vec2(1.,.0)/R.x, lvl)  -  T(uv + vec2(1.,.0)/R.x, lvl),
        T(uv - vec2(.0,1.)/R.y, lvl)  -  T(uv + vec2(.0,1.)/R.y, lvl),
        1.
    ));
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/R;
  
    vec3 col = texture(iChannel0, uv).rgb;

    vec3 sn = calcNormal(uv); // Surface Normal
    vec3 sp = vec3(uv-.5, 2.); // Surface Position
    vec3 rd = normalize(vec3(uv-.5, 1.)); // Ray direction orig to screen space
    vec3 lp = vec3(.0,.0, 1.9); // Light Position
    vec3 ld = lp - sp; // Light direction
    float lDist = max(length(ld), .0001);
    ld /= lDist;
    float atten = .8/(1. + lDist * lDist*.2);


    float diff = max(dot(-sn, ld), .0);// diffuse lightning

    vec3 ldf = vec3(ld.xy, ld.z*.1);
    float fresnel = pow( 1. + dot(sn ,ldf),  5.)*1.; // fresnel lightning

    col = col * vec3(fresnel + 2. + diff)*.25;

    fragColor = vec4(vec3(col),1.0);
}
