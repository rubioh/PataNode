#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D input_texture;
uniform sampler2D LightsBuffer;

#define R iResolution.xy

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy;
  
    vec3 col = texelFetch(input_texture, ivec2(uv), 0).rgb;

    vec2 test = texelFetch(LightsBuffer, ivec2(3,0), 0).xy;

    test *= 0.0001;
    col += test.xyx;
    //col += texelFetch(LightsBuffer, ivec2(gl_FragCoord.xy), 0).rgb;

    fragColor = vec4(col,1.0);
}



