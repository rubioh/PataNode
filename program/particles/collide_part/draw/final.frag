uniform sampler2D iChannel0;
uniform sampler2D TrailImg;

uniform float wait_final;

void main(){
    
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    vec3 part = texture(TrailImg, uv).rgb;
    vec3 shader = texture(iChannel0, uv).rgb;
    shader = clamp(shader, vec3(0.), vec3(1.));

    float L = clamp(length(shader), 0, 1);
    vec3 col = mix(shader, part*wait_final, (1.-L)*(1.-wait_final) + wait_final);

    fragColor = vec4(col, 1.);
}
