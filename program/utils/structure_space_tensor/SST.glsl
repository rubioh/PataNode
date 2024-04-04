#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform sampler2D iChannel0;

void main()
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;

    vec4 g = texture(iChannel0, uv);
    float lambda1 = .5*(g.x + g.y + sqrt(g.y*g.y - 2.*g.y*g.x + g.x*g.x + 4.*g.z*g.z));
    vec2 d = vec2(-g.x + lambda1, -g.z);
    if (d.x>0) d *= -1.;

    vec4 res = (length(d) >= 0.0000001) ? vec4(normalize(d), sqrt(lambda1), 1.) : vec4(0.,0.1,0.,1.);
    fragColor = res ; //(res+1.)/2.;
}
