#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform float width;
uniform float radius;
uniform float y_offset;
uniform float iTime;
uniform float x_offset;
uniform float nrj;

#define time iTime*.1
#define pi 3.14159
#define tau 6.283



float sdArc( in vec2 p, in vec2 sc, in float ra, float rb )
{
    // sc is the sin/cos of the arc's aperture
    p.x = abs(p.x);
    return ((sc.y*p.x>sc.x*p.y) ? length(p-sc*ra) :
                                  abs(length(p)-ra)) - rb;
}

float sdBox( in vec2 p, in vec2 b )
{
    vec2 d = abs(p)-b;
    return length(max(d,0.0)) + min(max(d.x,d.y),0.0);
}

float arch(vec2 uv){
    float orig_width = .3;
    float orig_radius = .7;

    float angle = 3.14159;
    vec2 sc = vec2(cos(angle), sin(angle));
    float ra = orig_radius*radius;
    float rb = orig_width*width;
    float height_rec = .5;

    float d = length(uv)-ra+rb;

    vec2 p = uv + vec2(0., .5);
    vec2 b = vec2(ra-rb, height_rec);
    d = min(d, sdBox(p, b));

    d *= -1;
    return d;
}

vec3 hash23(vec2 p){
    vec3 N = vec3(
        dot(p, vec2(17.123, 11.256)),
        dot(p, vec2(123.456, 178.632)),
        dot(p, vec2(1789.355, 7453.225))
        );
    return vec3(fract(sin(N.x*1298.568)*369), fract(sin(N.y*12.356)*456), fract(sin(N.z*178.459)*123));
}



// rotate position around axis
vec2 rotate(vec2 p, float a)
{
    return vec2(p.x * cos(a) - p.y * sin(a), p.x * sin(a) + p.y * cos(a));
}

// 1D random numbers
float rand(float n)
{
    return fract(sin(n) * 43758.5453123);
}

// 2D random numbers
vec2 rand2(in vec2 p)
{
    return fract(vec2(sin(p.x * 591.32 + p.y * 154.077), cos(p.x * 391.32 + p.y * 49.077)));
}

// 1D noise
float noise1(float p)
{
    float fl = floor(p);
    float fc = fract(p);
    return mix(rand(fl), rand(fl + 1.0), fc);
}


// voronoi distance noise, based on iq's articles
float voronoi(in vec2 x)
{
    vec2 p = floor(x);
    vec2 f = fract(x);
    
    vec2 res = vec2(8.0);
    for(int j = -1; j <= 1; j ++)
    {
        for(int i = -1; i <= 1; i ++)
        {
            vec2 b = vec2(i, j);
            vec2 r = vec2(b) - f + rand2(p + b);
            
            // chebyshev distance, one of many ways to do this
            float d = max(abs(r.x), abs(r.y));
            
            if(d < res.x)
            {
                res.y = res.x;
                res.x = d;
            }
            else if(d < res.y)
            {
                res.y = d;
            }
        }
    }
    return res.y - res.x;
}


void main()
{
    vec2 R = iResolution.xy;
    vec2 uv = (gl_FragCoord.xy*2.-R)/R.y;

    uv.y += y_offset;
    uv.x += x_offset;

    float arc = arch(uv);
    float tmparc = arc;
    arc = smoothstep(0.01, 0., arc)*smoothstep(1.25, .3, -arc);

    uv *= 2.5;
    float v = 0.0;
    float flicker = noise1(iTime * .25) * 0.8 + 0.4;
   vec2 suv = uv;
    // that looks highly interesting:
    //v = 1.0 - length(uv) * 1.3;
    
    
    // a bit of camera movement
    uv *= 0.6 + sin(iTime * 0.01) * 0.4;
    
    
    // add some noise octaves
    float a = 0.6, f = 1.0;
    float tmp = pow(fract(iTime*.4), 1.);
    float t = floor(iTime*.4) + mix(fract(iTime*.4), tmp, step(tmp, .5));
    for(int i = 0; i < 3; i ++) // 4 octaves also lookok nice, its getting a bit slow though
    {   
        float v1 = voronoi(uv * f + 5.0);
        float v2 = 0.0;
        
        // make the moving electrons-effect for higher octaves
        if(i > 0)
        {
            // of course everything based on voronoi
            v2 = voronoi(uv * f * 0.5 + 50.0 - vec2(0., t*.5));
            
            float va = 0.0, vb = 0.0;
            va = 1.0 - smoothstep(0.0, 0.1, v1);
            vb = 1.0 - smoothstep(0.0, 0.08, v2);
            v += a * pow(va * (0.5 + vb), 2.0);
        }
        
        // make sharp edges
        v1 = 1.0 - smoothstep(0.0, 0.3, v1);
        
        // noise is used as intensity map
        v2 = a * (noise1(v1 * 5.5 + 0.1));
        
        // octave 0's intensity changes a bit
        if(i == 0)
            v += v2 * flicker;
        else
            v += v2;
        
        f *= 3.0;
        a *= 0.7;
    }

    // slight vignetting
    v *= exp(-0.6 * length(suv)) * 1.2;
    
    // use texture channel0 for color? why not.
    uv *= .33;
    vec3 cexp = vec3(noise1(uv.x*0.1 + uv.y+17.888)* 3.0, noise1(uv.x + uv.y*0.1+137.), noise1(uv.x + uv.y*17.5*0.1+8.)) + 
                vec3(noise1(uv.x*0.01 + uv.y )* 3.0, noise1(uv.x + uv.y*0.01+17.), noise1(uv.x + uv.y*0.01+8.));//vec3(1.0, 2.0, 4.0);
    cexp *= 1.2;
    
    // old blueish color set
    //vec3 cexp = vec3(6.0, 4.0, 2.0);
    
    vec3 col = vec3(pow(v, cexp.x), pow(v, cexp.y), pow(v, cexp.z)) * 2.0;

    col = pow(col, vec3(.7));
    vec4 color = vec4(col+nrj*.001, 1.);


    fragColor = arc*color;
}
