#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;
uniform float gamma;
uniform float compression;

#define R iResolution

vec3 RomBinDaHouseToneMapping(vec3 color)
{
    color = exp( -1.0 / ( compression*color + .04 ) );
	color = pow(color, vec3(1. / gamma));
	return color;
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy;

    vec3 col = texture(iChannel0, uv/R).rgb;
    col = RomBinDaHouseToneMapping(col);
    fragColor = vec4(col, 1.0);

}
