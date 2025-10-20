#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float mode;
uniform float smooth_low;
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

vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));

    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(
        abs(q.z + (q.w - q.y) / (6.0 * d + e)),
        d / (q.x + e),
        q.x
    );
}
vec3 hsv2rgb(vec3 c) {
    vec3 rgb = clamp( abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0 );
    return c.z * mix(vec3(1.0), rgb, c.y);
}

float hash(float x) {
    return fract(sin(x) * 43758.5453123);
}

float noise1d(float x) {
    float i = floor(x);
    float f = fract(x);
    
    float u = f * f * (3.0 - 2.0 * f); // smoothstep interpolation

    return mix(hash(i), hash(i + 1.0), u);
}

vec2 vertical_band(vec2 uv){
    uv -= .5;
    float mask = 1;
    float pos = 0.;
	if (on_tempo < .5)
		pos = on_tempo*2 + cos(iTime)*.0001;
	else
		pos = on_tempo*-2 + 2;
	pos -= .5;
	pos *= .8;
	mask = smoothstep(.01, .0, abs(uv.x-pos)-.1*(2 + 1*cos(on_tempo*4*3.14159+1.45)));

	float hue_shift = 1. - pow(abs(uv.x-pos), 4.)*200.;
    return vec2(mask, hue_shift); // black
}

vec2 random_blink(vec2 uv){
	float mask = noise1d(uv.x*30. + kick_count*20.);
	mask = pow(mask+.1, 8.);
	float hue_shift = cos(uv.x*2.*3.1415 + on_tempo)*.5;
    return vec2(mask, hue_shift); // black
}

vec2 center_expandX(vec2 uv) {
    float x = uv.x * 2.0 - 1.0;

    float dist = abs(x); // distance au centre horizontal

    float mask = smoothstep(0.0, .1, 10.*smooth_low*dist); // se propage depuis le centre jusqu'à A
	mask *= .0001;
	if (mod(kick_count, 8) < 4){
    	mask += smoothstep(0.0, .1, (cos(on_tempo*2.*3.14159)*.5+.5)*dist); 
	}
	else
    	mask += 1-smoothstep(0.0, .1, (cos(on_tempo*2.*3.14159)*.5+.5)*dist); 

	float hue_shift = 1.;
    return vec2(mask, hue_shift); // valeur entre 0 et 1
}
vec2 movingPacket(vec2 uv) {
	
	float packetWidth = .5;
	float speed = 1.;
	float t = noise_time*.05;
	float x = uv.x;

    float totalRange = 1.0;
    float numPackets = floor(totalRange / packetWidth);
    
    // Combien de temps prend un paquet pour avancer
    float timePerPacket = 1.0 / speed;

    // Période complète = aller + retour
    float cycleTime = numPackets * timePerPacket * 2.0;

    float localTime = mod(t, cycleTime);
    
    // Allée ou retour ?
    bool reverse = localTime > numPackets * timePerPacket;
    float phase = reverse
        ? 2.0 * numPackets * timePerPacket - localTime
        : localTime;

    // Quel paquet est en mouvement actuellement ?
    float activeIndex = floor(phase / timePerPacket);
    float progress = fract(phase / timePerPacket);

    // Position du paquet actif
    float packetStart = activeIndex * packetWidth;
    float packetEnd = packetStart + packetWidth * progress;

    // Affichage du paquet en déplacement
    float mask = step(packetStart, x) * step(x, packetEnd);
	return vec2(mask, 1.);
}
vec2 fancy1DEffect(vec2 uv) {
    float x = uv.x;

    // Paramètres artistiques
    float speed = 0.05;
    float freq = 6.0;
    float wave = sin((x + noise_time * speed) * freq);

    // Ondes secondaires (modulées dans le temps)
    float ripple = sin((x * 20.0 + sin(noise_time * 0.5 * .01) * 2.0) + noise_time * .1);

    // Bruit sinusoïdal stylisé
    float mask = smoothstep(0.0, 0.2, wave * 0.5 + 0.5) *      // forme d'onde
                 smoothstep(0.3, 1.0, ripple * 0.5 + 0.5);     // pulsation fine

    // Pulsation douce au centre
    mask *= smoothstep(0.0, 0.5, x) * smoothstep(1.0, 0.5, x); // centrage

    return vec2(mask, 1.0);
}
vec2 fancy1DBlocks(vec2 uv) {
    float x = uv.x;

    // Paramètres
    float blockSize = 0.16;                // taille des blocs
    float t = noise_time * 0.01;           // vitesse
    float shift = floor(mod(x + t, 1.0) / blockSize);  // index du bloc
    float local = fract((x + t) / blockSize);          // position locale

    // Animation en dent de scie dans le bloc
    float pulse = smoothstep(0.1, 0.0, abs(local - 0.5) * 2.0);

    // Modulation en fonction de l'index (onde sinus)
    float modulator = sin(shift * 1.5 + noise_time * .2) * 0.5 + 0.5;

    float mask = pulse * modulator;

    return vec2(mask, 1.0);
}
vec2 fancy1DEcho(vec2 uv) {
    float x = uv.x;
    float time = noise_time*.05;

    // Distance au centre (0.5 = milieu de l'écran horizontalement)
    float dist = abs(x - 0.5);

    // Génère une onde qui se propage
    float wave = sin((dist - time * 0.4) * 20.0);

    // Atténuation naturelle vers les bords
    float falloff = exp(-dist * 8.0);

    // Crée un masque ondulant qui pulse vers l’extérieur
    float mask = smoothstep(0.0, 0.3, wave) * falloff;

    return vec2(mask, 1.0);
}
vec2 fancy1DGlitch(vec2 uv) {
    float x = uv.x;
    float blockSize = 0.05;

    // Quel bloc sur l'axe x ?
    float id = floor(x / blockSize);

    // Génère une "hauteur" pseudo-aléatoire qui évolue dans le temps
    float val = hash(id + floor(kick_count));

    // Crée des bandes activées ou non selon une valeur seuil
    float threshold = 0.5 + 0.4 * sin(kick_count * 0.7 * .1 + id);
    float mask = step(threshold, val);

    return vec2(mask, 1.0);
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
	col = 0.00001*col;

    uv = gl_FragCoord.xy/R;
    st = uv;
	mask *= .0001;
	float hue_shift = 0.;
	if (mode == 0){
		vec2 res = vertical_band(uv);
		mask = res.x;
		hue_shift = (1.-res.y)*.2;
	}
	if (mode == 1){
		vec2 res = random_blink(uv);
		mask = res.x;
		hue_shift = (1.-res.y)*.2;
	}
	if (mode == 2){
		vec2 res = center_expandX(uv);
		mask = res.x;
		hue_shift = (1.-res.y)*.2;
	}
	if (mode == 3){
		vec2 res = movingPacket(uv);
		mask = res.x;
		hue_shift = (1.-res.y)*.2;
	}
	if (mode == 4){
		vec2 res = fancy1DEffect(uv);
		mask = res.x;
		hue_shift = (1.-res.y)*.2;
	}
	if (mode == 5){
		vec2 res = fancy1DBlocks(uv);
		mask = res.x;
		hue_shift = (1.-res.y)*.2;
	}
	if (mode == 6){
		vec2 res = fancy1DEcho(uv);
		mask = res.x;
		hue_shift = (1.-res.y)*.2;
	}
	if (mode == 7){
		vec2 res = fancy1DGlitch(uv);
		mask = res.x;
		hue_shift = (1.-res.y)*.2;
	}

	col = texture(iChannel0, uv).rgb * mask + col*.00001;

	vec3 hsv = rgb2hsv(col);
	hsv.x += hue_shift;

	col = hsv2rgb(hsv);

    fragColor = vec4(col,1.0);

}
