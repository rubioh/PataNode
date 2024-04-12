#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float tz;
uniform float tr;
uniform float tf;
uniform float th;
uniform float mode;
uniform float mini_chill;
uniform float energy;
uniform float mode_sym;
uniform float cnt_beat;
uniform float thp;
uniform float iTime;
#define PI 3.14159

float hash(float i){
    return fract(sin(i*34.54987)*17.5465);
}

float opSmoothUnion( float d1, float d2, float k ) {
    float h = clamp( 0.5 + 0.5*(d2-d1)/k, 0.0, 1.0 );
    return mix( d2, d1, h ) - k*h*(1.0-h); }

float sdSphere(vec3 p, float r )
{
  return length(p) - r;
}
mat2 rotate2d(float a){

    return mat2(cos(a), sin(a), -sin(a), cos(a));

}
float sdHexPrism( vec3 p, vec2 h )
{
  const vec3 k = vec3(-0.8660254, 0.5, 0.57735);
  p = abs(p);
  p.xy -= 2.0*min(dot(k.xy, p.xy), 0.0)*k.xy;
  vec2 d = vec2(
       length(p.xy-vec2(clamp(p.x,-k.z*h.x,k.z*h.x), h.x))*sign(p.y-h.x),
       p.z-h.y );
  return min(max(d.x,d.y),0.0) + length(max(d,0.0));
}
float smin( float d1, float d2, float k )
{
    float h = clamp( 0.5 + 0.5*(d2-d1)/k, 0.0, 1.0 );
    return mix( d2, d1, h ) - k*h*(1.0-h);
}
float ssub( float d1, float d2, float k )
{
    float h = clamp( 0.5 - 0.5*(d2+d1)/k, 0.0, 1.0 );
    return mix( d2, -d1, h ) + k*h*(1.0-h);
}
float sdRoundBox( vec3 p, vec3 b, float r )
{
  vec3 q = abs(p) - b;
  return length(max(q,0.0)) + min(max(q.x,max(q.y,q.z)),0.0) - r;
}
float sdRoundedCylinder( vec3 p, float ra, float rb, float h )
{
  vec2 d = vec2( length(p.xz)-2.0*ra+rb, abs(p.y) - h );
  return min(max(d.x,d.y),0.0) + length(max(d,0.0)) - rb;
}
float sdCapsule( vec3 p, vec3 a, vec3 b, float r )
{
  vec3 pa = p - a, ba = b - a;
  float h = clamp( dot(pa,ba)/dot(ba,ba), 0.0, 1.0 );
  return length( pa - ba*h ) - r;
}

float map_hand(vec3 p, float IDX)
{
  float d = 1e10;
  float SF = .1;
  float size_f = .24;

  float Lp = .6; // Phalange length
  float t = tf;
  float tK = tz + (IDX+1.)*.5*3.14159;
  float t1 = mix(mod(t*1., 2.*PI), tK, mode*(1-mini_chill));
  float t2 = mix(mod(t*.95, 2.*PI), tK, mode*(1-mini_chill));
  float t3 = mix(mod(t*1.05, 2.*PI), tK, mode*(1-mini_chill));
  float t4 = mix(mod(t*1.10, 2.*PI), tK, mode*(1-mini_chill));
  float t5 = mix(mod(t*1.15, 2.*PI), tK, mode*(1-mini_chill));
  int i = 0;
  vec3 q = p;
  vec3 S0 = vec3(.0,.0,.0);
  vec3 S1 = vec3(.0,.0,Lp);
  S1.yz *= rotate2d(.5 - .3*cos(t1));
  S1 += S0;
  vec3 S2 = vec3(.0,.0, Lp);
  S2.yz *= rotate2d(-.2 + .2*cos(t1) );
  S2 += S1;
  vec3 S3 = vec3(.0,.0,Lp*.8);
  S3.yz *= rotate2d(-.5 + .5*cos(t1));
  S3 += S2;


  float df = sdCapsule(q, S0, S1, size_f);
  df = smin(df, sdCapsule(q, S1, S2, size_f), SF);
  df = smin(df, sdCapsule(q, S2, S3, size_f), SF);


  vec3 Sm1 = vec3(.15,.05,Lp*1.3);
  Sm1.yz *= rotate2d(.8);
  Sm1 = S0-Sm1;
  df = smin(df, sdCapsule(q, S0, Sm1, size_f), SF*1.5);
  vec3 Sm2 = vec3(.05,.2,Lp*.8);
  Sm2.yz *= rotate2d(.8);
  Sm2 = Sm1-Sm2;
  df = smin(df, sdCapsule(q, Sm1, Sm2, size_f), SF*2.);
  d = smin(d, df, .1);


  i = 1;
  q = p-vec3(.5, -.2,.0);
  q.xz *= rotate2d(-.2);
  S0 = vec3(.0,.0,.0);
  S1 = vec3(.0,.0,Lp);
  S1.yz *= rotate2d(.5 - .3*cos(t2));
  S1 += S0;
  S2 = vec3(.0,.0,Lp);
  S2.yz *= rotate2d(-.2 + .2*cos(t2) );
  S2 += S1;
  S3 = vec3(.0,.0,Lp*.8);
  S3.yz *= rotate2d(-.5 + .5*cos(t2));
  S3 += S2;
  df = sdCapsule(q, S0, S1, size_f);
  df = smin(df, sdCapsule(q, S1, S2, size_f), SF);


  Sm1 = vec3(.1,.0,Lp*1.3);
  Sm1.yz *= rotate2d(.8);
  Sm1 = S0-Sm1;
  df = smin(df, sdCapsule(q, S0, Sm1, size_f), SF*1.5);
  Sm2 = vec3(.15,.1,Lp*.4);
  Sm2.yz *= rotate2d(.8);
  Sm2 = Sm1-Sm2;
  df = smin(df, sdCapsule(q, Sm1, Sm2, size_f), SF*2.);
  d = smin(d, df, .1);


  i = 2;
  q = p+vec3(.5,-.2,.0);
  q.xz *= rotate2d(.2);
  S0 = vec3(.0,.0,.0);
  S1 = vec3(.0,.0,Lp);
  S1.yz *= rotate2d(.5 - .3*cos(t3));
  S1 += S0;
  S2 = vec3(.0,.0,Lp);
  S2.yz *= rotate2d(-.2 + .2*cos(t3) );
  S2 += S1;
  S3 = vec3(.0,.0,Lp*.8);
  S3.yz *= rotate2d(-.5 + .5*cos(t3));
  S3 += S2;
  df = sdCapsule(q, S0, S1, size_f);
  df = smin(df, sdCapsule(q, S1, S2, size_f), SF);
  df = smin(df, sdCapsule(q, S2, S3, size_f), SF);


  Sm1 = vec3(.1,.1,Lp*1.8);
  Sm1.yz *= rotate2d(.8);
  Sm1 = S0-Sm1;
  df = smin(df, sdCapsule(q, S0, Sm1, size_f), SF*1.5);
  Sm2 = vec3(.0,.2,Lp*.8);
  Sm2.yz *= rotate2d(.8);
  Sm2 = Sm1-Sm2;
  df = smin(df, sdCapsule(q, Sm1, Sm2, size_f), SF*2.);
  d = smin(d, df, .1);


  i = 3;
  q = p+vec3(1.,.0,.0);
  q.xz *= rotate2d(.3);
  S0 = vec3(.0,.0,.0);
  S1 = vec3(.0,.0,Lp);
  S1.yz *= rotate2d(.5 - .3*cos(t4));
  S1 += S0;
  S2 = vec3(.0,.0,Lp);
  S2.yz *= rotate2d(-.2 + .2*cos(t4) );
  S2 += S1;
  S3 = vec3(.0,.0,Lp*.8);
  S3.yz *= rotate2d(-.5 + .5*cos(t4));
  S3 += S2;

  df = sdCapsule(q, S0, S1, size_f);
  df = smin(df, sdCapsule(q, S1, S2, size_f), SF);
  df = smin(df, sdCapsule(q, S2, S3, size_f), SF);

  Sm1 = vec3(.1,.0,Lp*1.6);
  Sm1.yz *= rotate2d(.8);
  Sm1 = S0-Sm1;
  df = smin(df, sdCapsule(q, S0, Sm1, size_f), SF*1.5);
  Sm2 = vec3(.0,.2,Lp*.8);
  Sm2.yz *= rotate2d(.8);
  Sm2 = Sm1-Sm2;
  df = smin(df, sdCapsule(q, Sm1, Sm2, size_f), SF*2.);
  d = smin(d, df, .1);


  // Thumb
  i = 4;
  q = p+vec3(1.5,1.,.0);
  q.xz *= rotate2d(.3);
  q.xy *= rotate2d(3.14159/2.);
  S0 = vec3(.0,.0,.0);
  S1 = vec3(.0,.0,Lp*.6);
  S1.yz *= rotate2d(-.2 - .5*cos(t5));
  S1 += S0;
  S2 = vec3(.0,.0,Lp);
  S2.yz *= rotate2d(-.4 - .4*cos(t5) );
  S2 += S1;
  df = sdCapsule(q, S0, S1, size_f*1.2);
  df = smin(df, sdCapsule(q, S1, S2, size_f*1.2), SF);

  Sm1 = vec3(.2,.0,Lp*1.4);
  Sm1.yz *= rotate2d(.3);
  Sm1 = S0-Sm1;
  df = smin(df, sdCapsule(q, S0, Sm1, size_f*1.2), SF*1.5);
  d = smin(d, df, .1);

  return d;
}


float map_finger(vec3 p, float IDX)
{
  float d = 1e10;
  float SF = .1;
  float size_f = .24;

  float Lp = .6; // Phalange length
  float t = tf;
  float tK = tz + (IDX+1.)*.5*3.14159;
  float t1 = mix(mod(t*1., 2.*PI), tK, mode*(1-mini_chill));
  float t2 = mix(mod(t*.95, 2.*PI), tK, mode*(1-mini_chill));
  float t3 = mix(mod(t*1.05, 2.*PI), tK, mode*(1-mini_chill));
  float t4 = mix(mod(t*1.10, 2.*PI), tK, mode*(1-mini_chill));
  float t5 = mix(mod(t*1.15, 2.*PI), tK, mode*(1-mini_chill));

  float di[5] = float[5](0,0,0,0,0);

  int i = 0;
  vec3 q = p;
  vec3 S0 = vec3(.0,.0,.0);
  vec3 S1 = vec3(.0,.0,Lp);
  S1.yz *= rotate2d((.5 - .3*cos(t1))*2.);
  S1 += S0;
  vec3 S2 = vec3(.0,.0, Lp);
  S2.yz *= rotate2d((-.2 + .2*cos(t1))*2. );
  S2 += S1;
  vec3 S3 = vec3(.0,.0,Lp*.8);
  S3.yz *= rotate2d((-.5 + .5*cos(t1))*2.);
  S3 += S2;
  float df = sdCapsule(q, S0, S1, size_f);
  df = smin(df, sdCapsule(q, S1, S2, size_f), SF);
  df = smin(df, sdCapsule(q, S2, S3, size_f), SF);
  float d0 = df;


  i = 1;
  q = p-vec3(.5, -.2,.0);
  q.xz *= rotate2d(-.2);
  S0 = vec3(.0,.0,.0);
  S1 = vec3(.0,.0,Lp);
  S1.yz *= rotate2d((.5 - .3*cos(t2))*2.);
  S1 += S0;
  S2 = vec3(.0,.0,Lp);
  S2.yz *= rotate2d((-.2 + .2*cos(t2))*2. );
  S2 += S1;
  S3 = vec3(.0,.0,Lp*.8);
  S3.yz *= rotate2d((-.5 + .5*cos(t2))*2. );
  S3 += S2;
  df = sdCapsule(q, S0, S1, size_f);
  df = smin(df, sdCapsule(q, S1, S2, size_f), SF);
  df = smin(df, sdCapsule(q, S2, S3, size_f), SF);
  float d1 = df;


  i = 2;
  q = p+vec3(.5,-.2,.0);
  q.xz *= rotate2d(.2);
  S0 = vec3(.0,.0,.0);
  S1 = vec3(.0,.0,Lp);
  S1.yz *= rotate2d((.5 - .3*cos(t3))* 2.);
  S1 += S0;
  S2 = vec3(.0,.0,Lp);
  S2.yz *= rotate2d((-.2 + .2*cos(t3) ) * 2.);
  S2 += S1;
  S3 = vec3(.0,.0,Lp*.8);
  S3.yz *= rotate2d((-.5 + .5*cos(t3))* 2.);
  S3 += S2;
  df = sdCapsule(q, S0, S1, size_f);
  df = smin(df, sdCapsule(q, S1, S2, size_f), SF);
  df = smin(df, sdCapsule(q, S2, S3, size_f), SF);
  //d = smin(d, df, .1);
  float d2 = df;


  i = 3;
  q = p+vec3(1.,.0,.0);
  q.xz *= rotate2d(.3);
  S0 = vec3(.0,.0,.0);
  S1 = vec3(.0,.0,Lp);
  S1.yz *= rotate2d((.5 - .3*cos(t4))*2.);
  S1 += S0;
  S2 = vec3(.0,.0,Lp);
  S2.yz *= rotate2d((-.2 + .2*cos(t4) )*2.);
  S2 += S1;
  S3 = vec3(.0,.0,Lp*.8);
  S3.yz *= rotate2d((-.5 + .5*cos(t4))*2.);
  S3 += S2;
  df = sdCapsule(q, S0, S1, size_f);
  df = smin(df, sdCapsule(q, S1, S2, size_f), SF);
  df = smin(df, sdCapsule(q, S2, S3, size_f), SF);
  float d3 = df;

  // Thumb
  i = 4;
  q = p+vec3(1.2,1.,.0);
  q.xz *= rotate2d(.3);
  q.xy *= rotate2d(3.14159/2.);
  S0 = vec3(.0,.0,.0);
  S1 = vec3(.0,.0,Lp*.6);
  S1.yz *= rotate2d(.7 - .5*cos(t5));
  S1 += S0;
  S2 = vec3(.0,.0,Lp);
  S2.yz *= rotate2d(-.4 + .4*cos(t5) );
  S2 += S1;
  df = sdCapsule(q, S0, S1, size_f*1.2);
  df = smin(df, sdCapsule(q, S1, S2, size_f*1.2), SF);
  float d4 = df;
  //d = smin(d, df, .1);
  di[0] =d0;
  di[1] =d1;
  di[2] =d2;
  di[3] =d3;
  di[4] =d4;
  for (int i=0; i<5; i++){
      //if (hash(float(i) + cnt_beat*IDX)>.2)
        d = smin(d, di[i], .1);
  }

  return d;
}


float map(vec3 p, inout float df, inout float dp, inout float IDXH, inout float obj){

    float d = 1e10;

    vec3 q = p-vec3(.0,.55+.05*cos(th*4.), 1.);
    d = sdSphere(q, .45);

    q = p-vec3(.0,-.45-.05*cos(th*4.), 1.);
    d = opSmoothUnion(d, sdSphere(q, .5), 1.);

    if (d<0.001){
        obj = 1.;
    }

    q = p;
    float angle_rX = cos(tr*.1);
    if (mode == 1.){
        mat2 rot = rotate2d(angle_rX*.5);
        q.xy *= rot;
    }
    float IDX_hand = sign(q.x);
    float tmp = sign(q.x);
    IDX_hand = mix(IDX_hand, 1., mode_sym);
    IDXH = IDX_hand;
    //float scale = 2.+1.5*sin(tz + 3.14159*IDX_hand*.5);
    float scale = 6. - energy*.1;
    q *= scale;
    q.z *= -1.;
    q.z +=  -4. + 4.5*sin(tz + 3.14159*IDX_hand*.5);
    //q.xy *= Rot;
    q.x = abs(q.x);
    q.x -= 2.5;
    q.zy *= rotate2d(.2-.2*sin(tz+3.14159*IDX_hand*.5));
    if (mode == 1.){
        q.xy *= rotate2d(IDX_hand*angle_rX*.15-3.14159/2-.5);
    }
    else{
        q.xy *= rotate2d(cos(tr)*.5 - .6);
    }
    //df = (tmp == 1.) ? map_hand(q, IDX_hand)/scale : map_finger(q, IDX_hand)/scale;///scale;
    df = map_finger(q, IDX_hand)/scale;///scale;
    if (df<0.001){
        obj = 2;
    }
    //dp = d;
    d = min(d,df);

    return d;
}


void main()
{
    vec2 uv = (gl_FragCoord.xy-iResolution.xy*.5)/iResolution.y;

    vec3 ro = vec3(.0, .0, -3.);
    vec3 rd = normalize(vec3(uv, 1.5+.5*cos(th)));

    int i = 0;
    float d = .0;
    float depth = .0;
    float dmin = 100.;
    float edge = .0;
    float edge_p = .0;
    float d_p = .0;
    float d_f = 100.;
    float d_ef = .0;
    float d_ep = .0;
    float d_old = 1e10;
    float obj = .0;
    float fobj = .0;
    for (; i<25; i++){

        vec3 p = ro + rd*depth;

        /*float a = p.z*.5*cos(iTime*.5);
        p.xy *= mat2(cos(a), sin(a), -sin(a), cos(a));
        p.z += iTime*.5;
        p.y = p.y + sin(p.z + iTime*2.)*.1;*/
        float idxh = 0.;
        d = map(p, d_f, d_p, idxh, obj);
        depth += d*.7;
        dmin = min(abs(d), dmin);
        if (d_f<.02 - .01*cos(tz- 3.14159*.5*idxh)) {
            edge = 1. ; d_ef = depth;
        }
        //if (d_p<.04){edge_p = 1.; d_ep = depth;}
        if (d<.001 || depth>5.){ fobj = obj; break;}

    }
    if (dmin<.001) dmin = 100.;
    float edge_finger = (d_f<.001 && i<60) ? .0:edge;
    edge_p = (d_p<.001) ? .0: edge_p;
    vec3 col = vec3(float(i)*1./40. * smoothstep(10., 1., depth) * step(float(i), 59.));
    //fragColor = vec4(exp(-dmin*dmin*1000.), .0,.0,1.0);
    edge = max(edge_finger, edge_p);
    d_ef = max(d_ef, d_ep);
    fragColor = vec4(edge, d_ef, fobj, depth);
}
