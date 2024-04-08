uniform sampler2D IdxBuffer;
uniform float part_radius;

vec2 transform(vec2 p){
    p += 1.;
    return p/2.;
}

vec2 to_idx(vec2 p, vec2 tiling, vec2 os){
    return (floor(p*tiling)+os)/tiling;
}

float lengthp(vec2 p){
    p -= .5;
    float x = pow(abs(p.x), 8.);
    float y = pow(abs(p.y), 8.);
    return pow(x+y, 1./8.);
}

void main(){
    
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    vec2 tiling = iResolution.xy/part_radius*1.5;

    vec2 idx = to_idx(uv, tiling, vec2(0.));
    vec2 coord = fract(uv*tiling);

    vec4 info = texelFetch(IdxBuffer, ivec2(idx*iResolution), 0).xyzw;
    vec2 info_idx = to_idx(transform(info.xy), tiling, vec2(0.));
    float s = step(-.1, texture(IdxBuffer, uv).a);

    if (idx == info_idx){
        fragColor = vec4(info.xy, s, info.a);
        return;
    }
    fragColor.z = s;
    fragColor.x = step(.48, lengthp(coord));
}
