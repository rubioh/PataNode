#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform float width;
uniform float radius;
uniform float y_offset;
uniform float x_offset;
uniform float iTime;
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


void main()
{
    vec2 R = iResolution.xy;
    vec2 uv = (gl_FragCoord.xy*2.-R)/R.y;
    vec4 color = vec4(voronoi(uv * 4.));
    color.w += (width + radius + x_offset + y_offset + iTime) / 100000.;
    fragColor = color;
}
