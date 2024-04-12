#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D SST;
uniform sampler2D previous_SST;
uniform float mix_rate;

#define R iResolution

void main(){
    
    vec2 uv = gl_FragCoord.xy/R;
 
    vec4 col = texture(SST, uv);
    vec4 prev_col = texture(previous_SST, uv);

    fragColor = mix(col, prev_col, mix_rate);
}
