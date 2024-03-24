#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform float tm;
uniform float tz;
uniform float tp;
uniform float tptt;
uniform float mode_sym;
uniform float mode_ptt;
uniform float go_ptt;
uniform float go_arms;

vec2 hash22(vec2 p){
    return fract(  sin( vec2(
                            dot(p,vec2(178.357, 37.456)),
                            dot(p,vec2(54.678, 87.3965)))) * vec2(36.5657, 25.689));
}
float hash(float d){
    return fract(sin(d*21.45879)*14564.57);
}
float noise1(float p){
    float idx = floor(p);
    float f = fract(p);

    f = f*f*3.-2.*f*f*f;

    float h0 = hash(idx);
    float h1 = hash(idx+1.);

    return mix(h0, h1, f);
}
float noise(vec2 p){
    vec2 idx = floor(p);
    vec2 f = fract(p);

    f = f*f*3.-2.*f*f*f;

    float h00 = hash22(idx).x;
    float h01 = hash22(idx+vec2(0.,1.)).x;
    float h10 = hash22(idx+vec2(1.,0.)).x;
    float h11 = hash22(idx+vec2(1.,1.)).x;

    return mix(
                mix(h00, h01, f.y),
                mix(h10, h11, f.y),
            f.x);
}
float PeriodicNoise(float t, vec2 seed){
    t = t*3.14159;
    return noise(vec2(cos(t), sin(t)) + seed);

}

float sdBox( in vec2 p, float r, float t)
{
    float M = 6. + 4.*cos(tz*.05 + t*2.*3.14);
    return pow(pow(abs(p.x), M) + pow(abs(p.y), M), 1./M) - r-.1;
}

float smoothmin( float d1, float d2, float k )
{
    float h = clamp( 0.5 + 0.5*(d2-d1)/k, 0.0, 1.0 );
    return mix( d2, d1, h ) - k*h*(1.0-h);
}
float circular_noise(vec2 seed, float t){
    return noise(vec2(cos(t), sin(t)) + seed);
}

float sdCircle( vec2 p, vec2 offset, float r )
{
    return length(p - offset) - r;
}
float sdEllipse( in vec2 p, in vec2 ab )
{
    p = abs(p); if( p.x > p.y ) {p=p.yx;ab=ab.yx;}
    float l = ab.y*ab.y - ab.x*ab.x;
    float m = ab.x*p.x/l;      float m2 = m*m;
    float n = ab.y*p.y/l;      float n2 = n*n;
    float c = (m2+n2-1.0)/3.0; float c3 = c*c*c;
    float q = c3 + m2*n2*2.0;
    float d = c3 + m2*n2;
    float g = m + m*n2;
    float co;
    if( d<0.0 )
    {
        float h = acos(q/c3)/3.0;
        float s = cos(h);
        float t = sin(h)*sqrt(3.0);
        float rx = sqrt( -c*(s + t + 2.0) + m2 );
        float ry = sqrt( -c*(s - t + 2.0) + m2 );
        co = (ry+sign(l)*rx+abs(g)/(rx*ry)- m)/2.0;
    }
    else
    {
        float h = 2.0*m*n*sqrt( d );
        float s = sign(q+h)*pow(abs(q+h), 1.0/3.0);
        float u = sign(q-h)*pow(abs(q-h), 1.0/3.0);
        float rx = -s - u - c*4.0 + 2.0*m2;
        float ry = (s - u)*sqrt(3.0);
        float rm = sqrt( rx*rx + ry*ry );
        co = (ry/sqrt(rm-rx)+2.0*g/rm-m)/2.0;
    }
    vec2 r = ab * vec2(co, sqrt(1.0-co*co));
    return length(r-p) * sign(p.y-r.y);
}
float sdRoundedBox(vec2 p, vec2 b, vec2 offset, vec4 r )
{
    p -= offset;

    r.xy = (p.x>0.0)?r.xy : r.zw;
    r.x  = (p.y>0.0)?r.x  : r.y;
    vec2 q = abs(p)-b+r.x;
    return min(max(q.x,q.y),0.0) + length(max(q,0.0)) - r.x;
}

float sdUnevenCapsule( vec2 p, float r1, float r2, float h )
{
    p.x = abs(p.x);
    float b = (r1-r2)/h;
    float a = sqrt(1.0-b*b);
    float k = dot(p,vec2(-b,a));
    if( k < 0.0 ) return length(p) - r1;
    if( k > a*h ) return length(p-vec2(0.0,h)) - r2;
    return dot(p, vec2(a,b) ) - r1;
}

float dot2(vec2 p){
    return dot(p,p);
}

float sdSegment( in vec2 p, in vec2 a, in vec2 b )
{
    vec2 pa = p-a, ba = b-a;
    float h = clamp( dot(pa,ba)/dot(ba,ba), 0.0, 1.0 );
    return length( pa - ba*h );
}
float sdBezier( in vec2 pos, in vec2 A, in vec2 B, in vec2 C )
{
    vec2 a = B - A;
    vec2 b = A - 2.0*B + C;
    vec2 c = a * 2.0;
    vec2 d = A - pos;
    float kk = 1.0/dot(b,b);
    float kx = kk * dot(a,b);
    float ky = kk * (2.0*dot(a,a)+dot(d,b)) / 3.0;
    float kz = kk * dot(d,a);
    float res = 0.0;
    float p = ky - kx*kx;
    float p3 = p*p*p;
    float q = kx*(2.0*kx*kx-3.0*ky) + kz;
    float h = q*q + 4.0*p3;
    if( h >= 0.0)
    {
        h = sqrt(h);
        vec2 x = (vec2(h,-h)-q)/2.0;
        vec2 uv = sign(x)*pow(abs(x), vec2(1.0/3.0));
        float t = clamp( uv.x+uv.y-kx, 0.0, 1.0 );
        res = dot2(d + (c + b*t)*t);
    }
    else
    {
        float z = sqrt(-p);
        float v = acos( q/(p*z*2.0) ) / 3.0;
        float m = cos(v);
        float n = sin(v)*1.732050808;
        vec3  t = clamp(vec3(m+m,-n-m,n-m)*z-kx,0.0,1.0);
        res = min( dot2(d+(c+b*t.x)*t.x),
                   dot2(d+(c+b*t.y)*t.y) );
        // the third root cannot be the closest
        // res = min(res,dot2(d+(c+b*t.z)*t.z));
    }
    return sqrt( res );
}
vec2 map_pat(vec2 uv){


    // Circular Noise
    vec2 N = vec2(0.);
    float t = tptt;
    vec2 st = vec2(length(uv), atan(uv.x, uv.y));
    N.x = (circular_noise(vec2(uv*2.3+t), st.y));
    N.y = (circular_noise(vec2(uv*2.2+t), st.y));

    vec2 NUV1 = -.5 +vec2(circular_noise(vec2(0. + t*.15), 1.), circular_noise(vec2(10. + t*.15), 4.));
    vec2 NUV2 = -.5 +vec2(circular_noise(vec2(-10. + t*.75), 1.), circular_noise(vec2(20. + t*.85), 4.));
    NUV2 *= .25;
    uv.y -= .5;

    uv += NUV1;
    vec2 uvE = uv + NUV2;

    float d1 = sdUnevenCapsule(uv/4. +N*.04/4., .095, .13, .2)*4.;
    float d2 = sdUnevenCapsule(vec2(uv.x, -uv.y+.7)/4. +N*.04/4., .095, .14, .2)*4.;

    //float d1 = sdRoundedBox(uv/4. +N*.04/4., vec2(.2, .3), vec2(.0,.17), vec4(.19, .3, .19, .3));
    //float d2 = sdRoundedBox(uv/4. + N*.04/4., vec2(.2,.22), vec2(.0,-.24), vec4(.22));
    float d = smoothmin(d1, d2, .1);

    float ag = .2  + .05*cos(t*.85);
    mat2 re = mat2(cos(ag), sin(ag), -sin(ag), cos(ag));
    float dEl = sdEllipse(re*(uvE/4.5+vec2(-.08, .27)), vec2(.5,.15))*4.5;
    dEl = max(dEl, -sdEllipse(re*(uvE+vec2(-.08, .27)*4.5), vec2(.5,.15)));

    float dSillon = abs(dEl) - .03;
    dSillon = max(dSillon, -d);

    float thick_arms = .06;
    float dB = abs(sdBezier(uvE, vec2(-.4,-.5)+NUV2, -.5*vec2(1.2, 1.5), vec2(-.6,-1.)))-thick_arms;
    dB = min(dB, abs(sdBezier(uvE, vec2(.3,-.5)+NUV2, .5*vec2(1.5,-1.), vec2(1.6,-1.2)))-thick_arms);
    dB = min(dB, abs(sdBezier(uvE, vec2(.45,.4)+NUV2, vec2(.8,.2)- NUV2, vec2(1.2,.1)-NUV2*.5))-thick_arms);
    dB = min(dB, abs(sdBezier(uvE, vec2(-.5,.4)+NUV2, vec2(-1.2,.0) - NUV2, -NUV2*.5+vec2(-.7,.0)))-thick_arms);

    float arms = (dB < 0.) ? 1.: 0.;
    d = min(d, dEl);
    float df = min(dB, dEl);
    float thick_eyes = .06;
    float deye = abs(sdSegment(uv, vec2(-.1,.8), vec2(-.1,.9))) - thick_eyes;
    deye = min(deye, abs(sdSegment(uv, vec2(.2,.8), vec2(.2,.9))) - thick_eyes);
    df = min(df, deye);
    if (deye<.0) arms = 1.;

    //df = min(deye, dB);
    //if (df<.0) arms = 1.;
    if (go_ptt > 0. && mode_ptt != 1.){
        df = deye;
        arms = step(deye, .0);
        if (go_arms == 1.){
            df = min(min(df, dSillon), dB);
            arms = step(min(df, dSillon), .0);
       }
    }
    if (go_ptt<1.) arms = 0.;

    return vec2(df, arms);
}

float map(vec2 uv){
    float id = 2.*(hash(-1.)-.5);
    float PN = PeriodicNoise(tp*(hash(id)-.5)*2., vec2(id, id)+150.);
    vec2 pB = vec2(PeriodicNoise(tp*id*.1, vec2(id, id)), PeriodicNoise(tp*id*.1 + 17., vec2(id, id)))*3.*(PN-.5)*2.;
    float a = tp*.2;
    mat2 rB = mat2(cos(a), sin(a), -sin(a), cos(a));
    //float d = sdBox(uv*rB - pB, .5, floor(id*2.));
    float d = 1e10;

    for (float i=0.; i<16.; i++){
        id = 2.*hash(mod(i, 4))-1.;
        float id_m = 2.*hash(i)-1.;
        vec2 sid = vec2(1.);

        if (i>=4 && i<8) sid = mix(vec2(1.), vec2(1,-1), mode_sym);
        if (i>=8 && i<12) sid = mix(vec2(1.), vec2(-1,1), mode_sym);
        if (i>=12) sid = mix(vec2(1.), vec2(-1,-1), mode_sym);

        PN = PeriodicNoise(tp*(hash(id)-.5)*.1, vec2(id, id)+150.);
        pB = vec2(PeriodicNoise(tp*id*.01, vec2(id, id)), PeriodicNoise(tp*id*.1 + 17., vec2(id, id)))*7.*(PN-.5)*4.;
        a = tp*.1*(exp(id))*id*mix(atan(1.,1.), atan(sid.x, sid.y), mode_sym);
        rB = mat2(cos(a), sin(a), -sin(a), cos(a));

        float PNm = PeriodicNoise(tp*(hash(id_m)-.5)*.1, vec2(id_m, id_m)+150.);
        vec2 pBm = vec2(PeriodicNoise(tp*id_m*.01, vec2(id_m, id_m)), PeriodicNoise(tp*id_m*.1 + 17., vec2(id_m, id_m)))*7.*(PNm-.5)*4.;
        if (i>=4 && i<8) pB = mix(pBm, pB*vec2(1,-1), mode_sym);
        if (i>=8 && i<12) pB = mix(pBm, pB*vec2(-1,1), mode_sym);
        if (i>=12) pB = mix(pBm, pB*vec2(-1,-1), mode_sym);

        d = smoothmin(d, sdBox(uv*rB - pB*.5, .5*(.5+.5*sin(id*tp*.5 + id + tp*.5)), floor(id*2.)), .2);
    }

    return d;
}

float smooth_floor(float x){
    float m = fract(x);
    return floor(x) + (pow(m, 20.) - pow(1.-m, 20.) )/2.;
}


void main()
{
    vec2 uv = (gl_FragCoord.xy-.5*iResolution.xy)/iResolution.y;
    //vec2 uv2 = mix(uv, abs(uv), mode_sym);
    vec2 uv2 = uv;
    //uv2 = abs(uv);
    float d = map(uv2*7.);
    vec2 dp = map_pat(uv*7.);
    d = mix(d, dp.x, go_ptt);
    float X = 5. + 2.*cos(tm * .17);
    float idx =  floor(d*X);
    if (d<.0){
        d = .0;
        if (dp.y >= .5 && go_ptt>0){//(mode_ptt == 1. || go_ptt == 1.)){
            idx = -2.;
        }
        else{
            idx=-1.;
        }
    }
    float smth_idx = smooth_floor(d*X+4.);
    float coord = fract(d*X);
    fragColor = vec4(d, idx+1., coord, smth_idx);
}
