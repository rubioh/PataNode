#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float mode;
uniform float mode_mask;
uniform float blink_force;
uniform float kick_count;
uniform float no_sym_mode;
uniform float on_tempo;
uniform float real_kick_count;
uniform float black_mode;
uniform float go_strobe;
uniform float black;
uniform float noise_time;
uniform float mode_2_sym;
#define R iResolution
#define PI 3.14159

float rand(vec2 n) { 
	return fract(sin(dot(n, vec2(12.9898, 4.1414))) * 43758.5453);
}

float noise(vec2 p){
	vec2 ip = floor(p);
	vec2 u = fract(p);
	u = u*u*(3.0-2.0*u);
	
	float res = mix(
		mix(rand(ip),rand(ip+vec2(1.0,0.0)),u.x),
		mix(rand(ip+vec2(0.0,1.0)),rand(ip+vec2(1.0,1.0)),u.x),u.y);
	return res*res;
}

float get_mask(vec2 uv){
    if (mode_mask == 0){
        uv -= .5;
        float polar = atan(uv.y, uv.x)+PI;
        polar += PI/2 * kick_count;
        polar = mod(polar, 2*PI);
        return 1.-step(PI/2, polar);
    }
    if (mode_mask == 1){
        uv -= .5;
        float polar = atan(uv.y, uv.x)+PI;
        polar += PI/2 * kick_count;
        polar = mod(polar, 2*PI);
        return 1.-step(PI, polar);
    }
    return 1.;
}

float get_no_sym_mask(vec2 uv){
    uv -= .5;
    float mask = 1;
    float pos = 0.;
    if (no_sym_mode == 0){
        float K = mod(real_kick_count, 8.)/8.;
        float a = atan(uv.y, uv.x);
        a += K*2.*3.14159+PI/8.;
        a = mod(a, 2*PI);
        mask = 1.-step(PI/4., a);
    }
    if (no_sym_mode == 1){
        float K = on_tempo;
        float a = atan(uv.y, uv.x);
        a += K*2.*3.14159;
        a = mod(a, 2*PI);
        mask = 1.-step(PI/4., a);
    }
    if (no_sym_mode == 2){
        float K = kick_count;
        if (K == 0) pos = -1.;
        if (K == 1) pos = 0.;
        if (K == 2) pos = 1.;
        if (K == 3) pos = 0.;
        pos *= .25;
        mask = smoothstep(.01, .0, abs(uv.y-pos)-.2);
    }
    if (no_sym_mode == 3){
        float K = kick_count;
        if (K == 0) pos = -1.;
        if (K == 1) pos = 0.;
        if (K == 2) pos = 1.;
        if (K == 3) pos = 0.;
        pos *= .25;
        mask = smoothstep(.01, .0, abs(uv.x-pos)-.2);
    }
    if (no_sym_mode == 4){
        if (on_tempo < .5)
            pos = on_tempo*2;
        else
            pos = on_tempo*-2 + 2;
        pos -= .5;
        pos *= .8;
        mask = smoothstep(.01, .0, abs(uv.x-pos)-.2);
    }
    return mask;
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/R;
    vec2 st = uv;
    vec3 col = vec3(0.);
    
    float mask = 1;
    if (mode == 0)
        uv.x = abs(uv.x-.5)+.25;
        mask = get_mask(uv);
        col = texture(iChannel0, uv).rgb;
    if (mode == 1)
        uv.y = abs(uv.y-.5)+.25;
        mask = get_mask(uv);
        col = texture(iChannel0, uv).rgb;
    if (mode >= 2){
        if (mode_2_sym <= 2){
            uv.x = abs(uv.x-.5)+.5;
            if (mode_2_sym <= 1)
                uv.y = abs(uv.y-.5)+.5;
        }
        mask = get_no_sym_mask(uv);
        col = texture(iChannel0, uv).rgb;
    }
    col = col*mask*blink_force;
    if (black == 1.){
        if (black_mode == 0)
            col *= 0.;
        if (black_mode == 1){
            float phi = noise(st*4. + noise_time*8.);
            col = texture(iChannel0, st).rgb;
            col *= pow((cos(phi*2.*3.14159)*.5+.5), 6.);
        }
    }
    if (go_strobe == 1){
        float s = cos(on_tempo*4*2.*3.14159)*.5+.5;
        s = pow(s, 3.);
        st.x = abs(st.x)-.5;
        col += s*get_mask(st)*.00001;
    }
    //col = mix(col, 1.-col, smoothstep(.2, .4, length(col)));
    fragColor = vec4(col,1.0);

}
