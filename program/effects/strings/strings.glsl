#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float on_chill;
uniform float change_seed;
uniform float stop;
#define R iResolution

float hash(float d){
    return fract(sin(d*17.546)*123.78);
}

float noise(float d){
    float f = fract(d);
    float i = floor(d);
    float d0 = hash(i);
    float d1 = hash(i+1);
    return mix(d0, d1, f);
}



void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy;


    float time =  iTime *.5;
    vec3 orig = clamp(texture(iChannel0, uv/R).rgb, vec3(0.), vec3(1.));
    if (on_chill == 1. || stop != 0){ 
        fragColor = vec4(orig, 1.);
        return;
    }

    vec3 col = orig*(.5+.5*cos(time*13.12))*2.;
    col += vec3(cos(.73 + uv.x/R.x*3.12*sin(time*0.05)), sin(.12 + uv.y/R.y*2.*cos(time*.07)), cos(.27 + uv.x/R.x*17.*sin(time*.004)))*
           (.5+.5*vec3(cos(time*.1), cos(time*.17), cos(time*.221)))*2.;

    float dr = 2. + .5*cos(time*2.33+uv.x/R.x); 
    float dg = 3. + .5*cos(time*17.33+uv.y/R.x); 
    float db = 40. + 39*cos(time*7.33+uv.x/R.x); 

    vec2 gridr = (fract(uv/R*R.x/dr)-.5)*2.; 
    vec2 gridg = (fract(uv/R*R.x/dg)-.5)*2.; 
    vec2 gridb = (fract(uv/R*R.x/db)-.5)*2.; 

    float Gr = length(pow(abs(gridr), vec2(10.)))+.5*cos(time);
    float Gg = length(pow(abs(gridg), vec2(10.)))+.5*cos(time*.95+.37);
    float Gb = length(pow(abs(gridb), vec2(10.)))+ .5*sin(time*.73);

    col = pow(col, (vec3(Gr*cos(time*0.47), Gg*cos(time*0.213), Gb*cos(time*1.23))*.7+.3)*5.);

        
    float mask = step(.5, noise(uv.x/(hash(change_seed)*30.) + change_seed+ time*.1));

    col = col*mask + (1.-col)*(1.-mask);
    
    col = clamp(col, vec3(0.), vec3(1.));

    col = mix(col, vec3(1.)*max(col.r, max(col.g, col.b)), .5);
    col = pow(col, vec3(2.2));
    fragColor = vec4(col, 1.0);

}
