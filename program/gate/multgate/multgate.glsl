#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform float energy;
uniform float drywet;


void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution.xy;
    
    vec4 tex1 = texture(iChannel0, uv);
    vec4 tex2 = texture(iChannel1, uv);



    vec4 col = tex1*tex2+energy*.00001;
    col = mix(tex1, col, drywet);
    col = col*.00001 + tex1 + tex2;

    fragColor = col;
}
