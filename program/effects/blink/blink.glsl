#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform float NRJ_LOW;
uniform vec2 iResolution;
uniform sampler2D iChannel0;

#define R iResolution

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/R;
  
    vec3 col = texture(iChannel0, uv).rgb;

    col = mix(vec3(0.), col, min(1., NRJ_LOW));

    fragColor = vec4(vec3(col),1.0);
}
