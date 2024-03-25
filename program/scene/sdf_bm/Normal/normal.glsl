#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;

uniform float tm;
uniform float tc;
uniform sampler2D iChannel0;
uniform float go_idx;
uniform float go_idx2;
uniform float goBloom_arms;
uniform float mode_ptt;

vec2 hash22(vec2 p){
    return fract(  sin( vec2(
                            dot(p,vec2(178.357, 37.456)),
                            dot(p,vec2(54.678, 87.3965)))) * vec2(36.5657, 25.689));
}
float hash(float d){
    return fract(sin(d*21.45879)*14564.57);
}
float noise1(float p){
    float idx = floor(p);
    float f = fract(p);

    f = f*f*3.-2.*f*f*f;

    float h0 = hash(idx);
    float h1 = hash(idx+1.);

    return mix(h0, h1, f);
}

#define T(p) pow(texture(iChannel0, p).a, 2.)
#define R iResolution

vec3 palette(float t){
    vec3 a = vec3(0.204,0.396,0.643);
    vec3 b = vec3(0.361,0.208,0.400);
    vec3 c = vec3(1., 1., 1.);
    vec3 d = vec3(0.306,0.604,0.024)*.1;
    return a + b*cos( 6.28318*(c*t+d) );
}

vec3 calcNormal(vec2 p) {
    vec2 e = vec2(1.0, -1.0) * 0.0001; // epsilon
    float orig = T(p);
    return normalize(
      vec3( T(p - vec2(.5,.0)/R.x) - T(p + vec2(.5,.0)/R.x),
             T(p - vec2(.0,.5)/R.y) - T(p + vec2(0.,.5)/R.y),
            1.));
}

void main()
{
    vec2 uv = gl_FragCoord.xy/R.xy;
    vec3 info = texture(iChannel0, uv).rgb;
    float d = info.x, idx = info.y, coord = info.z;

    vec3 col = palette(hash(idx)*10. + tc* .1)*(.4+.6*pow(noise1(cos(idx*1.-.3*tc)+tc*.1), 4.))*4.;
    // Bump Mapping
    vec3 sn = calcNormal(uv); // Surface normal
    vec3 sp = vec3(uv, idx); // Surface position.
    vec3 rd = normalize(vec3(uv-.5, 1.)); // Direction vector from the origin to the screen plane.
    vec3 lp = vec3(-.5,-.5, -1.); // Light position
 	vec3 ld = lp - sp; // Light direction
	float lDist = max(length(ld), 0.001);
	ld /= lDist;
    float atten = .8/(1.0 + lDist*lDist*0.2);

	float diff = max(dot(-sn, ld), 0.);
    vec3 ldf = vec3(-ld.xy, ld.z);
    float fresnel = pow( 1.+ dot(sn, ldf), 5. );


    atten = mix((idx == go_idx) ? 1. : (idx == go_idx2) ? 1.: atten, atten*goBloom_arms, mode_ptt);
    atten = mix(atten*.75, atten, mode_ptt);
    col = mix(col, mix(col, vec3(.7,.1,.1), goBloom_arms*.75), mode_ptt);
    col = atten*col*vec3(diff+fresnel)*.2;

    float goBloom = (idx == go_idx) ? 1.: (idx == go_idx2) ? 1. : .0;
    float arms_bloom = .0;
    if (idx == -1.){
        col.rgb = vec3(.7, .05, .05);
        arms_bloom = goBloom_arms;
    }
    if (mode_ptt == 1.){
        goBloom *= .3;
    }

    fragColor = vec4(clamp(vec3(col), vec3(0.), vec3(1.)), goBloom*6. + arms_bloom*5.)*4.;
}
