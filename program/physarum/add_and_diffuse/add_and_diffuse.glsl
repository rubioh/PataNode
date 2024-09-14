#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D AddTexture;
uniform sampler2D BaseTexture;

uniform float decay_rate;
uniform float diffuse_amount;

#define R iResolution
#define s(x, y, sampler) texture(sampler, (gl_FragCoord.xy+vec2(x,y))/iResolution.xy)

vec4 diffuse(vec4 center){
    vec4 L = vec4(0.);
    vec4 v00 = .5*s(-1, 1, BaseTexture),  v10 = s(0, 1, BaseTexture), v20 = .5*s(1, 1, BaseTexture),
         v01 = s(-1, 0, BaseTexture),                          v21 = s(1, 0, BaseTexture),
         v02 = .5*s(-1,-1, BaseTexture),  v12 = s(0,-1, BaseTexture), v22 = .5*s(1,-1, BaseTexture);
    return (center + v00 +v01 + v02 + v10 + v12 + v20 + v21 + v22)/7*diffuse_amount + (1.-diffuse_amount)*center;
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/R;
  
    vec4 orig = texture(BaseTexture, uv).rgba;
    vec4 to_add = texture(AddTexture, uv).rgba;
        
    orig += to_add;
    orig = diffuse(orig);
    orig *= decay_rate;
    
    orig = clamp(orig, vec4(-100.), vec4(100.));
    fragColor = vec4(orig);
}
