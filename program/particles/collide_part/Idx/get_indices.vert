#version 330 core

in vec4 in_vert;
in vec3 in_col;

out vec4 out_vert;
out vec3 out_col;

uniform sampler2D TileIdx;
uniform vec2 iResolution;
uniform float part_size;
uniform float part_radius;

#define W iResolution.x/iResolution.y/2

ivec2 get_tile(vec2 tile_base, vec2 offset_){
    return ivec2( (tile_base + offset_)*iResolution);
}

vec2 transform(vec2 p){
    p = p+1.;
    p = p/2.;
    p *= iResolution;
    return p / iResolution.y;
}

vec2 itransform(vec2 p){
    p *= iResolution.y;
    p /= iResolution;
    p *= 2.;
    return p-1.;
}

vec2 solveCollision(vec2 pos, vec4 id2){
    if (id2.w == gl_VertexID)
        return pos;
    pos = transform(pos);
    vec2 pos2 = transform(id2.xy);
    
    vec2 col_axis = pos-pos2;
    float dist = length(col_axis);
    float rad_tot = W*part_radius;
    if (dist<rad_tot){
        vec2 n = col_axis/dist;
        float delta = .5*(rad_tot-dist);
        pos += delta*n;
    }
    return itransform(pos);
}

void main() {
    //color = vec3(1., gl_VertexID/N, 0.);
    vec2 pos = in_vert.xy;
    
    vec2 uv = (pos+1.)/2.;
    vec2 tiling = iResolution.xy/part_size*2;
    vec2 tile_base = uv;

    vec4 pos1 = texelFetch(TileIdx, get_tile(tile_base, vec2(1,1)/tiling), 0);
    pos = solveCollision(pos, pos1);
    vec4 pos2 = texelFetch(TileIdx, get_tile(tile_base, vec2(-1,1)/tiling), 0);
    pos = solveCollision(pos, pos2);
    vec4 pos3 = texelFetch(TileIdx, get_tile(tile_base, vec2(1,-1)/tiling), 0);
    pos = solveCollision(pos, pos3);
    vec4 pos4 = texelFetch(TileIdx, get_tile(tile_base, vec2(-1,-1)/tiling), 0);
    pos = solveCollision(pos, pos4);
    vec4 pos5 = texelFetch(TileIdx, get_tile(tile_base, vec2(0,1)/tiling), 0);
    pos = solveCollision(pos, pos5);
    vec4 pos6 = texelFetch(TileIdx, get_tile(tile_base, vec2(1,0)/tiling), 0);
    pos = solveCollision(pos, pos6);
    vec4 pos7 = texelFetch(TileIdx, get_tile(tile_base, vec2(-1,0)/tiling), 0);
    pos = solveCollision(pos, pos7);
    vec4 pos8 = texelFetch(TileIdx, get_tile(tile_base, vec2(0,-1)/tiling), 0);
    pos = solveCollision(pos, pos8);

    out_vert = vec4(pos, in_vert.zw);
    out_col = in_col;
}
