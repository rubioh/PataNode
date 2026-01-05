#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform float hue;
uniform float hue2;
uniform float strobe;
uniform vec2 iResolution;

vec3 HUEtoRGB(in float hue)
{
    hue = fract(hue);
    vec3 rgb = abs(hue * 6. - vec3(3, 2, 4)) * vec3(1, -1, -1) + vec3(-1, 2, 2);
    return clamp(rgb, 0., 1.);
}

// Some of the functions here were borrowed from http://mercury.sexy/hg_sdf/
// Repeat only a few times: from indices <start> to <stop> (similar to above, but more flexible)
float pModInterval1(inout float p, float size, float start, float stop) {
	float halfsize = size*0.5;
	float c = floor((p + halfsize)/size);
	p = mod(p+halfsize, size) - halfsize;
	if (c > stop) { //yes, this might not be the best thing numerically.
		p += size*(c - stop);
		c = stop;
	}
	if (c <start) {
		p += size*(c - start);
		c = start;
	}
	return c;
}
float hash11(float p)
{
    p = fract(p * .1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

// https://www.shadertoy.com/view/4djSRW
vec2 hash22(vec2 p)
{
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.xx + p3.yz) * p3.zy);
}
float voronoi(vec2 uv)
{

    float m = 112.0;

    float m2 = m;
    for (int i = -2; i < 2; ++i)
    {
        for (int j = -2; j < 2; ++j)
        {

            vec2 coords = vec2(i, j);
            vec2 tmp = floor(uv + coords);
            vec2 id = vec2(.3 * sin(iTime * hash22(tmp))) + tmp;

            float new_m = length(uv - id);
            if (new_m < m)
            {
                m2 = m;
                m = new_m;
            }
        }
    }
    return m * m * m * .7;
}

// Repeat around the origin by a fixed angle.
// For easier use, num of repetitions is use to specify the angle.
float pModPolar(inout vec2 p, float repetitions)
{
    float angle = 2. * 3.1415 / repetitions;
    float a = atan(p.y, p.x) + angle / 2.;
    float r = length(p);
    float c = floor(a / angle);
    a = mod(a, angle) - angle / 2.;
    p = vec2(cos(a), sin(a)) * r;
    // For an odd number of repetitions, fix cell index of the cell in -x direction
    // (cell index would be e.g. -5 and 5 in the two halves of the cell):
    if (abs(c) >= (repetitions / 2.))
        c = abs(c);
    return c;
}

// Cylinder standing upright on the xz plane
float fCylinder(vec3 p, float r, float height)
{
    float d = length(p.xz) - r;
    d = max(d, abs(p.y) - height);
    return d;
}

// The "Round" variant uses a quarter-circle to join the two objects smoothly:
float fOpUnionRound(float a, float b, float r)
{
    vec2 u = max(vec2(r - a, r - b), vec2(0));
    return max(r, min(a, b)) - length(u);
}
vec2 rotate2d(vec2 p, float f)
{
    mat2 a = mat2(cos(f), -sin(f), sin(f), cos(f));

    return a * p;
}

vec2 balls(vec3 p)
{
    float mat = 0.0;
    p.x *= 1.4;
    p.x += sin(p.y * 4. + iTime * 2.) / 4.;

    p.xz *= min(-0.5, p.y / 2. - 1.);

    //    p.xz *= p.y;
    pModPolar(p.xz, 6.);

    p.x -= .3;

    float r = .2;
    //    p.y = mod(p.y, r) - r / 2.;

    p.y += 3.9;
    mat = floor( ( p.y ) / r);
    float t = floor( mod(-iTime * 24., 22.)  );
    mat = p.y / r;
    if (mat > 22. || mat < 1.) {
        mat = 0.;
    }
    
    pModInterval1(p.y, r, 0., 22.);
    return vec2(length(p) - .12, mat);
}

vec4 tentacle(vec3 p)
{

    vec3 pp = p;
    float mat = 0.0;
    vec2 b = balls(p);
    float sp = length(pp * vec3(.7 + cos(iTime) / 16., 1.2, 1.) - vec3(0., 1.2, 0.)) - .7;

    p.x += sin(p.y * 4. + .8 + iTime * 3.) / 5.;

    pModPolar(p.xz, 8.);
    p.x -= .4;
    float tentacle = fCylinder(p, .02, .9);
    float inner_sphere = length(pp * vec3(1.1, 1.5, .7) - vec3(sin(iTime * 2.) / 8., 1.6, 0.)) - .5;
    float o = min(b.x, fOpUnionRound(sp, tentacle, .3));
    //    inner_sphere = sp / 2.;
    if (inner_sphere < o)
    {
      //  mat = 1.0;
    }

    return vec4(o, 0.0, mat, b.y);
}


vec4 mapjellyfish(vec3 p)
{
    // p.x += mod(iTime * 2., 15.) - 15.;

    float r = 5.;

    float id = floor(p.x / r - iTime / r);
    p.y += (hash11(id) - .5) * 6.;
    p.x = mod(p.x - iTime, r) - r / 2.;

    //    p.x -= mod( iTime * 2., 15.) - 7.5;
    p.z -= 12.;
    vec4 ret = tentacle(p.yxz);
    return vec4(ret.x, 1.0, ret.z, ret.w);
}

float sea(vec3 p)
{
//return 0.;
    float ret = 0.;
    float amp = .8;
    float freq = .5;

    for (int i = 0; i < 5; ++i)
    {
        ret += (sin(p.y * freq + iTime * amp) + cos(p.x * freq - iTime)) * amp;

        amp /= 1.5;
        freq *= 2.1;
    }
    return ret;
}

vec4 mapsea(vec3 p)
{
    return vec4(-p.z + 20. + sea(p), 2., p.x / 2. - 5., iTime / 2. + p.y / 2. - 5.);
}

vec4 mapalgua(vec3 p) {
    p.x = abs(p.x);
    p.z -=.8;  
    p.x -= .5;
    p.y -= .2;
    
    p.y += sin(p.z * 5. + iTime ) / 25.;
    p.x += sin(p.y * 5.) / 12.;
    
    float r = .1;
    p.y = mod(p.y, r) - r / 2.;
    float d = fCylinder(p.xzy, .005,.9);
 //   float d = fCylinder(p, .02, .9);
    
    return vec4(d, 3., 0., 0.);
}


vec4 map(vec3 p)
{

    vec4 d = mapjellyfish(p);

    vec4 nd = mapsea(p);
    if (nd.x < d.x)
    {
        d = nd;
    }
    
    nd = mapalgua(p);
    if (nd.x < d.x)
    {
        d = nd;
    }



    return d;
}


vec4 raymarch(vec3 ro, vec3 rd)
{

    float t = 0.;
    for (int i = 0; i < 200; ++i)
    {
        vec3 p = ro + rd * t;
        vec4 m = map(p);

        if (m.x < 0.001)
        {
            return m;
        }
        t += min(1.1, m.x * .6);
    }
    return vec4(0.);
}

vec4 mapBrain(vec3 p) {
    float r = 5.;

    float id = floor(p.x / r - iTime / r);
    p.y += (hash11(id) - .5) * 6.;
    p.x = mod(p.x - iTime, r) - r / 2.;

    p.z -= 12.;
    float b = length(p.xyz / vec3(1.,1.3,1.)- vec3(1.1, sin(iTime * 2.) / 8., .0 ) ) - .3;
    return vec4(b, 1.0, 0., 0.);

}
vec4 mapstar(vec3 p) {

    p.z -= 20.;
    p.x += 3. + p.y;
    p.y += mod(iTime * 2., 12.) - 6.;
    return vec4( length(p) - 1., 3., 0., 0.);
}

vec4 map2(vec3 p) {
    vec4 d;
    vec4 nd = mapBrain(p);
    d = nd;
    nd = mapstar(p);
    if (nd.x < d.x)
    {
        //d = nd;
    }
    return vec4( d );
}

// https://iquilezles.org/articles/normalsSDF
vec3 calcNormal(in vec3 pos)
{
    vec2 e = vec2(1.0, -1.0) * 0.5773;
    const float eps = 0.0005;
    return normalize(e.xyy * map(pos + e.xyy * eps).x +
                     e.yyx * map(pos + e.yyx * eps).x +
                     e.yxy * map(pos + e.yxy * eps).x +
                     e.xxx * map(pos + e.xxx * eps).x);
}

vec4 rm2(vec3 ro, vec3 rd)
{
    float t = 0.;
    for (int i = 0; i < 200; ++i)
    {
        vec3 p = ro + rd * t;
        vec4 m = map2(p);

        if (m.x < 0.001)
        {
            return m;
        }
        t += min(1.1, m.x * 1.);
    }
    return vec4(0.);
}
void main()
{
    vec2 txuv = (gl_FragCoord.xy / iResolution.xy);
    vec2 uv = (gl_FragCoord.xy - iResolution.xy / 2.0) / iResolution.xx;

    vec3 ro = vec3(0.);
    vec3 rd = normalize(vec3(uv.x, uv.y, 1.0));

    vec4 c = raymarch(ro, rd);
    vec3 p = ro + rd * c.x;

    vec3 tx = vec3(voronoi(txuv)) * .4;
    tx += vec3(.005, .2, .6) * .5;
    vec4 c2 = rm2(ro, rd);
    vec3 p2 = ro + rd * c2.x;
    vec3 n = calcNormal(p);
    // Jellyfish material
    if (c.y == 1.)
    {

        fragColor = vec4(vec3(.02, .2, .3), 1.0);

        if (c2.y == 1.0)
        {
            fragColor += .6 * vec4(3.*vec3(.8, .5, .5) * vec3(voronoi(uv.xy * 100. + vec2(iTime * -10., 0.))), 1.0);
        }

        if (c.w > -0.)
        {
            fragColor  += (22.-c.w) / 22.;
        }
    }
    else if (c.y == 2.0)
    {
        vec3 sun = vec3(1.) * smoothstep(.9, .1, length((uv - vec2(.2, .1)) * 3.)) * .5;

        vec3 tx = vec3(voronoi(vec2(c.z, c.w) / .5));

        fragColor = vec4(sun + tx * HUEtoRGB(hue2) + 2. * HUEtoRGB(hue) / 5., 1.0);
        
    if (c2.y == 3.) {
        fragColor *= .2;
    }

    } else if (c.y == 3.0) {
        fragColor = vec4(vec3(.1, .2, .2), 1.);
    }
    if (strobe > 1.) {
        if (fract(iTime * 100) < 0.5) {
            fragColor = vec4(0.);
        } else {
            fragColor = pow(fragColor, vec4(2.));
        }
    }
    
}
