#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform sampler2D iChannel0;
uniform float dry_wet;

void sort2(inout vec4 a0, inout vec4 a1) {
	vec4 b0 = min(a0, a1);
	vec4 b1 = max(a0, a1);
	a0 = b0;
	a1 = b1;
}

void sort(inout vec4 a0, inout vec4 a1, inout vec4 a2, inout vec4 a3, inout vec4 a4) {
	sort2(a0, a1);
	sort2(a3, a4);
	sort2(a0, a2);
	sort2(a1, a2);
	sort2(a0, a3);
	sort2(a2, a3);
	sort2(a1, a4);
	sort2(a1, a2);
	sort2(a3, a4);
}

#define R iResolution

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    vec4 c0 = texture(iChannel0, uv + vec2(-2, 0)/R );
    vec4 c1 = texture(iChannel0, uv + vec2( -1, 0)/R );
    vec4 c2 = texture(iChannel0, uv + vec2( 0, 0)/R );
    vec4 c3 = texture(iChannel0, uv + vec2(-1, 0)/R );
    vec4 c4 = texture(iChannel0, uv + vec2( -2,0)/R );
    vec4 c5 = texture(iChannel0, uv + vec2( 0, -2)/R );
    vec4 c6 = texture(iChannel0, uv + vec2(0,-1)/R );
    vec4 c7 = texture(iChannel0, uv + vec2( 0,-2)/R );
    vec4 c8 = texture(iChannel0, uv + vec2( 0,-1)/R );
    
    vec4 c9 = texture(iChannel0, uv + vec2( 1,1)/R );
    vec4 c10 = texture(iChannel0, uv + vec2( 1,1)/R );
    vec4 c11 = texture(iChannel0, uv + vec2( -1,-1)/R );
    vec4 c12 = texture(iChannel0, uv + vec2( -1,-1)/R );

    vec4 c13 = texture(iChannel0, uv + vec2( -1,1)/R );
    vec4 c14 = texture(iChannel0, uv + vec2( -1,1)/R );
    vec4 c15 = texture(iChannel0, uv + vec2( 1,-1)/R );
    vec4 c16 = texture(iChannel0, uv + vec2( 1,-1)/R );

    sort(c0, c1, c2, c3, c4);
    sort(c5, c6, c2, c7, c8);
    sort(c9, c10, c2, c11, c12);
    sort(c13, c14, c2, c15, c16);
    //sort(c17, c18, c2, c19, c20);

    //sort(c5, c6, c2, c7, c8);
    
    vec4 color = c2;
    if (dry_wet == 20.589){
        color *= 2.;
    }

    fragColor = color;
}
