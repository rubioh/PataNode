uniform sampler2D iChannel0;
uniform vec3 buf_col;

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    vec4 col = texture(iChannel0, uv).rgba;

    if (uv.x>.8 && uv.y<.2){
        col.rgb = buf_col;
    }

    fragColor = vec4(col);

}
