#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform sampler2D UVState;
uniform sampler2D seed;
uniform float dt;
uniform float scale;
uniform float a;
uniform float on_kick;
uniform float energy;
uniform int iFrame;

#define T(uv, offset) texture(InkState, uv + offset)
#define S(a,b,c) smoothstep(a,b,c)

float hash(vec2 p){
    const vec2 k = vec2( 0.3183099, 0.3678794 );
    float n = 111.0*p.x + 113.0*p.y;
    return fract(n*fract(k*n)).x;
}

float noiseh(in vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    vec2 u = f*f*(3.0-2.0*f);
    return mix(a, b, u.x) +
            (c - a)* u.y * (1.0 - u.x) +
            (d - b) * u.x * u.y;
}

vec2 field(vec2 pos)
{
	float s = scale;
    float t = noiseh(vec2(iTime*.2, iTime*.2+100) + pos*3.)-.5;

	pos *= s;
	float n = noiseh(pos+t);

	float e = 0.1 + t*.5;
	float nx = noiseh(vec2(pos+vec2(e,0.)));
	float ny = noiseh(vec2(pos+vec2(0.,e)));

	return vec2(-(ny-n),nx-n)*2.;
}

float length_(vec2 uv){
    float N = 10.;
    float x = pow(abs(uv.x), N);
    float y = pow(abs(uv.y), N);
    return pow(x+y, 1./N);
}

void main()
{

    vec2 R = iResolution;
    vec2 uv = gl_FragCoord.xy/R;

    vec2 vel = field(uv);

    if (iFrame <= 0){
        fragColor = vec4(uv, 0., 0.);
        return;
    }
    vec2 advection = dt*vel/R*a*50.*(energy+ .2);
    vec2 mv_uv = uv + advection;
    mv_uv = clamp(mv_uv, vec2(0.), vec2(1.));
    vec2 last_uv = texture(UVState, mv_uv).rg;
    last_uv = clamp(last_uv, vec2(0.), vec2(1.));
    fragColor = vec4(mix(last_uv, uv, .1 + .2*length_(uv)), 0., 0.);//*.0001 + vec4(tex, 1.);
}

/*

    if (iFrame <= 0){
        fragColor = tex;
        return;
    }
    vec4 newink = tex*( (on_kick == 0.) ?  .3 : .9);//*S(.6, 0., length(uv-.5));


    vec4 ink = texture(InkState, uv + advection);
    ink.rgba = mix(ink.rgba, newink, min(length(newink.rgb)*2., 1.));

    ink *= (length(ink.rgb)>1.) ? .99 : .99;
    ink *= (on_kick == 1.)? 3. : .965;
    
    fragColor = ink;//*.0001 + vec4(tex, 1.);
    //fragColor.w = 1.;
}*/
