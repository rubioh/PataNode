#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform float energy_cum;
uniform float energy;
uniform float x0;
uniform float y0;
uniform float zoom_factor;

float hash21(vec2 p){
    vec2 d = vec2(17.256, 18.5679);
    return fract(sin(dot(p,d)*3.3628)*17.256);

}

float hash(float h){
    return fract(sin(h*173.456)*36.234);
}

float noise(vec2 p){
    vec2 pt = floor(p);
    vec2 pt1 = floor(p)+1.;
    float h = hash21(pt);
    float h1 = hash21(pt1);
    return mix(h, h1, fract(p.x));
}
float sdEquilateralTriangle( in vec2 p, in float r )
{
    const float k = sqrt(3.0);
    p.x = abs(p.x) - r;
    p.y = p.y + r/k;
    if( p.x+k*p.y>0.0 ) p = vec2(p.x-k*p.y,-k*p.x-p.y)/2.0;
    p.x -= clamp( p.x, -2.0*r, 0.0 );
    return -length(p)*sign(p.y);
}
float sdSegment( in vec2 p, in vec2 a, in vec2 b )
{
    vec2 pa = p-a, ba = b-a;
    float h = clamp( dot(pa,ba)/dot(ba,ba), 0.0, 1.0 );
    return length( pa - ba*h );
}

float sdZ(vec2 p){

    p.x *= 1.75;
    float d = sdSegment(p, vec2(-.4,-.2), vec2(.4,-.2));
    d = min(d, sdSegment(p, vec2(.4,-.2), vec2(-.4,.2)));
    d = min(d, sdSegment(p, vec2(-.4,.2), vec2(.4,.2)));

    return d;
}
mat2 rot(float angle){
    return mat2(cos(angle), sin(angle), -sin(angle), cos(angle));
}

vec4 palette(float t){
    return mix(
        mix(vec4(0.988,0.686,0.243,1), vec4(0.678,0.498,0.659,1), cos(t)*.5+.5),
        mix(vec4(0.451,0.824,0.086,1), vec4(0.204,0.396,0.643,1), cos(t)*.5+.5),
        cos(t*.07)*.5+.5);
}

#define R iResolution.xy
void main()
{
    vec2 I = gl_FragCoord.xy;
    vec2 uv = (R*.5-I.xy)/R.y;
    float t=energy_cum;
    //Clear frag and loop 100 times

    vec4 lum = vec4(0.);
    for (float i=.5; i>0.49; i-=.005){
        vec2 p=(I+I-R)/R.y*i;
        p *= 8. + 4.*sin(t*.03-3.1415/2.);
        p *= zoom_factor;
        vec2 P = p;
        p.x = p.x/.9;
        float deltay = noise(vec2(t)*.02 + floor(p.x));
        float deltax = noise(vec2(t)*.02 + floor(p.y));
        p.y += deltay*deltay*32*(1.-y0);
        p.x += deltax*deltax*32*(1.-x0);
        //p.y += mix(deltay*deltay*32., 0., y0);
        //p.x += mix(deltax*deltax*32., 0., x0);
        //Mirror quadrants
        //Add color and fade outward
        vec2 id = floor(p);
        float go_id = noise(id*17. + t*.3);
        go_id *= go_id;

        float angle = noise(t*.001+vec2(go_id))*4.;
        p = fract(p);
        p -= .5;
        p *= rot(angle*6.28);
        p*=1.5;
        vec2 q = p;
        float L2 = smoothstep(.05, .0, abs(sdEquilateralTriangle(p, .4))-.01);
        p = abs(p);
        float L = abs(max(abs(p.x), abs(p.y)))*4.;
        L = mix(abs(L - 1.), L2-1., .5+.5*cos(1.*t*(noise(vec2(hash21(id)))-.5)));

        float dZ = sdZ(q);
        float dO = abs(length(q)*4.-1.);
        float zozo =  mix(dZ, dO, .5+.5*cos(1.*t*(noise(vec2(hash21(id)))-.5)));

        float tMix = .5+.5*cos(.033*t + hash(hash21(id))*2.*3.1415);

        L = mix(L, zozo, tMix);

        float d = L;
        float LP = length(p);
        LP = 1./(1.+150.*LP*LP);
        float LUV = 1./(1.+10.*length(uv)*length(uv));
        vec4 c = palette(t*0.2 + i*6.2830*4.+tMix*3.14159);
        if (i==.5){
            lum += c*exp(-d*d*1000.)*(LUV*.1 + go_id) * LUV *4.* LP + c/(1.+400.*d*d)*go_id * LP * LUV;
        }
        else{
            c *= exp(-d*d*4000.*i)*go_id;
            float Di = abs(.5-i);
            lum += c/i*.1 /(1.+600.*Di*Di)*2. * .5 * (1.+energy*3.) * LUV*
                exp(-length(p)*length(p)*30.)*8.;
        }
    }
    //Tanh tonemap
    lum = tanh(lum*lum*(15 + 30*energy)*2.);
    fragColor = vec4(lum);
}
