#version 330 core
layout (location=0) out vec4 fragColor;
uniform float iTime;
uniform vec2 iResolution;
uniform float num_kick;

float hash(float d){
    return fract(sin(d*17.546)*123.78);
}

float sinwave(float p, float t) {
	float s = (1. + sin(p + t)) * .5;
	return s;
}


vec3 pal( in float t, in vec3 a, in vec3 b, in vec3 c, in vec3 d )
{
	return a + b*cos( 6.28318*(c*t+d) );
}

vec3 getcol(float x1) {

	float x2= fract(iTime / 4.);
	float x = fract(x1 / 1.);
//x2=0.;
vec3 cols[7] = vec3[7] (pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.0,0.33,0.67) ),
	pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.0,0.10,0.20) ),
	pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,1.0),vec3(0.3,0.20,0.20) ),
	pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,1.0,0.5),vec3(0.8,0.90,0.30) ),
	pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(1.0,0.7,0.4),vec3(0.0,0.15,0.20) ),
	pal( x, vec3(0.5,0.5,0.5),vec3(0.5,0.5,0.5),vec3(2.0,1.0,0.0),vec3(0.5,0.20,0.25) ),
	pal( x, vec3(0.5,1.5,0.4),vec3(0.6,0.4,0.9),vec3(2.0,1.5,1.0),vec3(0.0,0.25,0.25))
	);
return mix( cols[int(x2)], cols[int(mod(x2 + 1, 6.))] , fract(x2));
}


float getv(float p, float t) {
	float octos = 1. / 8.;

	return step(p, mod(t, 1.) )  * step(mod(t, 1.), p  + octos );
}
float getvv(float p, float t) {
	float octos = 1. / 8.;

	return smoothstep(0., p , mod(t, 1.) )  * smoothstep(0., mod(t, 1.), p  + octos );
}

float getvvv(float p, float t) {
	float octos = 1. / 8.;

	float e = smoothstep(0., p , mod(t, 1.) )  * smoothstep(0., mod(t, 1.), p  + octos );
	e = p-mod(t * octos,1.);
	return hash(floor(e / octos) * octos);
}

vec3 choose_effect(vec2 p) {
	float octos = 1./8.;	

//	return vec3(getv(p.x, octos * num_kick), 0., 0.); 
	return getcol( getvv(p.y, iTime)) * getv(p.x, num_kick * octos); 
	return vec3(getv(p.x, octos * num_kick), 0., 0.);
	float s1 = sinwave(p.x, num_kick / 1.9);
	float s2 = sinwave(p.x, iTime * 4.);

}

void main()
{
    vec2 p = (gl_FragCoord.xy / iResolution.yy ) / 2.;
 
 	vec3 col = choose_effect(p);
    
    fragColor = vec4(col,1.0 + iTime + num_kick);
}

