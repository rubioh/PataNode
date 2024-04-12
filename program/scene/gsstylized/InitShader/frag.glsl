#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D patate;
uniform int mode;

#define PI 3.14156

float lengthP(vec2 uv, float P){
    
    float x = pow(abs(uv.x), P);
    float y = pow(abs(uv.y), P);
    return pow(x+y, 1./P);
}

float Triangle(float radius){

    vec2 uv = (gl_FragCoord.xy-.5*iResolution.xy)/iResolution.y;

    uv *= 5.;
    uv.y += .1;
    int N = 3;

    // Angle and radius from the current pixel
    float a = atan(uv.x,uv.y)+PI;
    float r = 2.*PI/float(N);

    // Shaping function that modulate the distance
    float d = cos(floor(.5+a/r)*r-a)*length(uv)/radius;

    return step(1., d);
}

float square(vec2 uv, float radius){
    return 1.-step(radius, lengthP(uv, 25.));
}

float circle(vec2 uv, float radius){
    return 1.-step(radius+.4*radius, lengthP(uv, 2.));
}

float hexagone(float radius){
    vec2 uv = (gl_FragCoord.xy-.5*iResolution.xy)/iResolution.y;

    uv *= 5.;
    uv.y += .1;
    int N = 5;

    // Angle and radius from the current pixel
    float a = atan(uv.x,uv.y)+PI;
    float r = 2.*PI/float(N);

    // Shaping function that modulate the distance
    return 1.-smoothstep(radius-.3*radius, radius+.3*radius, lengthP(uv, 2.));
}

float get_patate(){
    return texture(patate, gl_FragCoord.xy/iResolution.xy).x;
}

void main()
{
    vec2 uv = (gl_FragCoord.xy-.5*iResolution.xy)/iResolution.y;

    vec3 col = vec3(1.);

    float m = 0.;
    if (mode == 0)
        m = square(uv, .15)*(1.-square(uv, .075));
    if (mode == 1)
        m = Triangle(.3)*(1.-Triangle(.7));
    if (mode == 2)
        m = circle(uv, .15)*(1.-circle(uv, .075));
    if (mode == 3)
        m = circle(uv, .15)*(1.-circle(uv, .075));

    col.y = m;

    fragColor = vec4(col, 1.);
}
