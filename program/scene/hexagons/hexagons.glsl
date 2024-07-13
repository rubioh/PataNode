#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform float rotationSpeed;
uniform float offsetSpeed;
uniform float waveFrequency;
uniform float waveSpeed;
uniform float numLayer;
uniform float waveOffset;
uniform float res;
uniform float thickness;

#define PI 3.141593
vec3 palette(float t, vec3 a, vec3 b, vec3 c, vec3 d )
{
    return a + b*cos(6.28318*(c*t+d));
}
vec2 hash( vec2 p )
{
    //p = mod(p, 4.0); // tile
    p = vec2(dot(p,vec2(175.1,311.7)),
             dot(p,vec2(260.5,752.3)));
    return fract(sin(p+455.)*18.5453);
}

const vec2 s = vec2(1, 1.7320508);

float calcHexDistance(vec2 p)
{
    p = abs(p);
    return max(dot(p, s * .5), p.x);
}

vec4 calcHexInfo(vec2 uv)
{
    vec4 hexCenter = round(vec4(uv, uv - vec2(.5, 1.)) / s.xyxy);
    vec4 offset = vec4(uv - hexCenter.xy * s, uv - (hexCenter.zw + .5) * s);
    return dot(offset.xy, offset.xy) < dot(offset.zw, offset.zw) ? vec4(offset.xy, hexCenter.xy) : vec4(offset.zw, hexCenter.zw);
}
void main()
{
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;

    float c = 0.;
    uv *= 7. * res;
    int num_layer = int(numLayer);
    float wave = max(0., sin(waveOffset + length(uv) * 1. * waveFrequency - iTime * 5. * waveSpeed));

    vec3 col = palette( length(uv) / .2 + iTime, 
    vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.0,0.33,0.67));

    vec3 col2 = 2.*palette( length(uv) / 4. + iTime, 
    vec3(0.5,0.1,0.5),vec3(0.1,0.5,0.5),vec3(1.0,.3,1.0),vec3(0.0,0.33,0.67));
    
    vec3 col3 = palette( length(uv) / 15. + iTime / 2., 
    vec3(1.5,0.5,1.52),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.0,0.33,0.67));
    for (int i = 0; i < num_layer; ++i) {
        uv.x+= offsetSpeed * ( iTime / 200.);
        uv.y+=wave / 12.;
        float r = rotationSpeed * ( iTime / 6. );
        if (i == 1)
            r += rotationSpeed * ( iTime  / 6. );
        mat2 rot = mat2(cos(r), -sin(r), sin(r), cos(r));
        uv *= rot;
        vec4 hexInfo = calcHexInfo(uv);
        float totalDist = calcHexDistance(hexInfo.xy) + .1;
        // Output to screen
        float d = .5 - (( thickness - 7.) / 100.);

        float c1 = 3.*smoothstep(d - .01, d + .2, totalDist);
        if (i == 1) {
            c1 *= wave;
        }
        if (i == 2) {
            c1 *= (1.-wave);
        }
        c+=c1;
        uv *= 1.5;
    }

    vec3 o = c * col2 + c* col + (c) * col3 * wave * 2.;
    o = c * col3 + col2*wave / 6.;
    fragColor = vec4(o, 1.0);
}

