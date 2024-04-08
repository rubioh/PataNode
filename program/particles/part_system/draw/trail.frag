uniform sampler2D PartImg;
uniform sampler2D TrailImg;

uniform float wait_trail;

void main(){
    
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    vec3 part = texture(PartImg, uv).rgb;
    vec3 trail = texture(TrailImg, uv).rgb;

    vec3 col = mix(trail*.99, part, min(length(part), 1));

    col = mix(col, part, pow(wait_trail, 8.));

    fragColor = vec4(col, 1.);
}
