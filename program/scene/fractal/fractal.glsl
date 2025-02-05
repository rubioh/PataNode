#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform vec2 iMouse;
uniform float energy;
uniform vec3 color_a;
uniform vec3 color_b;
uniform vec3 color_c;
uniform vec3 color_d;

#define AaA 1.

float getHeight(vec2 p, float id){
    float res = .0;
    if (id == .0){
        res =  pow(texture(iChannel0, p).r, 1.)+.001;}
    if (id == 1.){
        res =  pow(texture(iChannel0, p).g, 1.)+.001;}
    if (id == 2.){
        res =  pow(abs(texture(iChannel0, p).b), 2)+.001;
        res += pow(abs(texture(iChannel0, p).r), 1.+energy);
        res += pow(abs(texture(iChannel0, p).w), 4.+energy);
    }
    else{
        res =  pow(texture(iChannel0, p).a, 1.)+.001;}
    return pow(res, energy+1.);
}


vec3 calcNormal(vec2 p, float id) {
    vec2 e = vec2(1.0, -1.0) * 0.001; // epsilon
    return normalize(
      e.xyy * getHeight(p + e.xy, id) +
      e.yyx * getHeight(p + e.yx, id) +
      e.xxx * getHeight(p + e.xx, id));
}

vec3 getLight(vec2 p, float id){
    vec3 sp = vec3(p, 0); // Surface position.
    vec3 rd = normalize(vec3(p, 1.)); // Direction vector from the origin to the screen plane.
    vec3 lp = vec3(iMouse.xy/iResolution.xy*0002.+ vec2(.5,2.), -0.85); // Light position
	vec3 sn = vec3(0., 0., -1); // Plane normal. Z pointing toward the viewer.
    
    // Using the gradient vector, "vec3(fx, fy, 0)," to perturb the XY plane normal ",vec3(0, 0, -1)." 
    sn = normalize(vec3(0.,0.,-1.)-calcNormal(p, id));           
    
    // LIGHTING
	// Determine the light direction vector, calculate its distance, then normalize it.
	vec3 ld = lp - sp;
	float lDist = max(length(ld), 0.001);
	ld /= lDist;  
    float atten = 1./(1.0 + lDist*lDist*0.05);

	// Diffuse value.
	float diff = max(dot(sn, ld), 0.);  
    // Specular highlighting.
    float spec = pow(max(dot( reflect(-ld, sn), -rd), 0.), 31.);

    return vec3(spec*(1.+sqrt(energy)*3.)+diff*.4 + .2)*.2;
}


// Primitive shape for the right l-system.

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = (gl_FragCoord.xy) / iResolution.xy;

    vec2 st = uv;
    vec3 fcol = vec3(0.);
    vec3 accum_tmp = vec3(0.);
    float W = 0.;
    #ifdef AA
    for (float i=-2.; i<.3; i+=.2){
        for (float j=-.2; j<.3; j+=.2){
    #else
            float i = 0.;
            float j = 0.;
    #endif


            vec2 offset_ = vec2(i,j)/iResolution.xy;
            vec4 dmin = texture(iChannel0, uv+offset_);
            
            vec3 a = vec3(0.204,0.396,0.643)*2.;
            vec3 b = vec3(0.125,0.290,0.529)*2.;
            vec3 c = vec3(0.447,0.624,0.812);

            vec3 col = vec3(.4,.8,.9);
            col = vec3(.1);


            vec3 tmp1 = (color_d+color_a)*.5*(1.-pow(dmin.w*4., 4.));
            vec3 tmp2 = color_b*(min(1.0, pow(dmin.y*(1.+(.5-.5*cos(iTime/1024.))), 1.+3.*(.5+.5*cos(iTime/1024.)))));
            vec3 tmp3 = color_a*(1.-pow(dmin.x, 2.));
            
            col = getLight(uv+offset_, 2)*vec3(1.);

            tmp1 = clamp(tmp1, vec3(0.), vec3(1.));
            tmp1 = mix(vec3(1.), tmp1, length(tmp1));
            tmp2 = clamp(tmp2, vec3(0.), vec3(1.));
            tmp2 = mix(vec3(1.), tmp2, length(tmp2));
            tmp3 = clamp(tmp3, vec3(0.), vec3(1.));
            tmp3 = mix(vec3(1.), tmp3, length(tmp3));

            col *= (2. + 3./(1.+pow(length(uv-.5)*1., 1.))*(pow(abs(dmin.g)*2., 2.)))*.2;
            col *= tmp1;
            col *= tmp3;
            col *= (1.5+.5*dmin.w)*.5;
            fcol += clamp(col, vec3(0.), vec3(1.));
            accum_tmp += tmp1;
            W += 1.;
    #ifdef AA
        }
    }
    #endif

    fcol /= W;
    accum_tmp /= W;
    float lum = smoothstep(.1, .2, length(1.-accum_tmp));
    fragColor = vec4(fcol, lum*6.*(4.+6.*energy));
}
