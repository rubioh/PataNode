#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;

uniform sampler2D iChannel0;
uniform sampler2D iChannel1;

void main() {
	vec2 ig = vec2(gl_FragCoord.xy);

	vec2 p = vec2(ig)/iResolution.xy;
	vec3 col1 = texture(iChannel0, p).xyz;
	vec3 col2 = texture(iChannel1, p).xyz;
	vec3 col = vec3(0.);

	if ((mod(int(gl_FragCoord.x+gl_FragCoord.y), 2) ) == 0 || (mod(int(gl_FragCoord.y), 2) ) == 0.1) {
		col1 = col2;
	}

    fragColor = vec4(col1, 1.0 );
}
