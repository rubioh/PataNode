#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D SubTexture;
uniform sampler2D BaseTexture;

uniform float substract_amount;

#define R iResolution

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/R;
  
    vec4 orig = texture(BaseTexture, uv).rgba;
    vec4 to_sub = texture(SubTexture, uv).rgba;
        
    orig -= to_sub*substract_amount;
    
    orig = clamp(orig, vec4(0.), vec4(1000.));
    fragColor = vec4(orig);
}
