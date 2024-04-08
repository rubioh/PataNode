#version 330 core

in vec4 in_pos;
in vec3 in_col;
out vec4 out_pos;
out vec3 out_col;

uniform float N;
uniform sampler2D particles;
uniform sampler2D TileIdx;
uniform float part_radius;
uniform float part_size;
uniform vec2 iResolution;

#define W iResolution.x/iResolution.y/2
#define T(a) texelFetch(TileIdx, ivec2(a), 0).xyw;

float hash(float x){
    return fract(sin(x*174.5783+.742)*1273.489);   
}

vec2 hash22(vec2 p){
    
    float x = dot(p, vec2(1783.5478,7489.57461));
    float y = dot(p, vec2(6893.4863, 4267.4863));
    return fract(sin(vec2(x,y)*13489.4567)*17.2638);
}

float get_radius(int i){    
    float rad = (hash(float(i))*part_radius-part_radius/2) + part_radius;
    return (part_radius)*W; // Hyper important le W
}

vec2 transform(vec2 p){
    p = p+1.;
    p = p/2.;
    p *= iResolution;
    return p/iResolution.y;
}

vec2 itransform(vec2 p){
    p *= iResolution.y;
    p /= iResolution;
    p *= 2.;
    return p-1;
}

vec2 solveCollision2(vec2 pos, out float n_col){
    pos = transform(pos);

    float rad_1 = get_radius(gl_VertexID);
    for (int i=0; i<int(N); i++){
        if (i == gl_VertexID)
            continue;
        vec2 pos2 = texelFetch(particles, ivec2(i, 0), 0).xy;
        pos2 = transform(pos2);
        vec2 collision_axis = pos-pos2;
        float dist = length(collision_axis);
        float rad_2 = get_radius(i);
        float rad_tot = rad_1 + rad_2;
        if (dist < rad_tot){
            vec2 n = collision_axis / dist;
            float delta = .5*(rad_tot - dist)*.1;
            pos += delta*n;
            n_col += 1;
        }
    }
    return itransform(pos);
}

#define NONE -10
vec3 castRay(vec2 ro, vec2 rd, vec2 tiling){
    float step_size = .2;
    float d = .1;
    vec2 march = rd;
    vec3 info = vec3(NONE);
    for (int i=0; i<25; i++){
        d += step_size;
        vec2 p = ro+rd*d/tiling;
        if (p.x<0 || p.x>1 || p.y<0 ||p.y>1) break;
        vec3 p2 = T(p*iResolution);
        if (p2.z == gl_VertexID || p2.z == NONE)
            continue;
        //if (p2.z >= 0 && p2.z !=gl_VertexID){
        info = p2;
        break;
        //}
    }
    return info;
}

vec2 solveCollision3(vec2 pos, out float n_col){
    n_col = 0;
    vec2 uv = (pos+1.)/2.;
    vec2 tiling = iResolution.xy/part_size*2;
    vec2 tile_1 = uv;
    //vec2 tile_1 = texelFetch(TileIdx, ivec2(idx*iResolution), 0).xy;
    //pos = texture(TileIdx, tile_1 + vec2(.5)/tiling).xy;
    pos = transform(pos);

    float rad_1 = get_radius(gl_VertexID);
    int K = 2;

    int past_id[8] = int[8](NONE,NONE,NONE,NONE,NONE,NONE,NONE,NONE);
    int indice = -1;
    vec2 dir[8] = vec2[8](vec2(0,1), vec2(1,0), vec2(0,-1), vec2(-1,0),
                          vec2(1,1), vec2(1,-1), vec2(-1,1), vec2(-1,-1));
    vec2 update = vec2(0.);
    for (int i=0; i<8; i++){
        indice += 1;
        vec2 rd = normalize(dir[i]);
        vec3 part_info = castRay(tile_1, rd, tiling);
        if (part_info.z == NONE)
            continue;

        // Check if already fetch this particles
        bool a = false;
        for (int k=0; k<8; k++){
            if (past_id[k] == int(part_info.z)){
                a = true;
            }
        }
        if (a) continue;

        past_id[indice] = int(part_info.z);
        vec2 pos2 = part_info.xy;
        pos2 = transform(pos2);
        vec2 collision_axis = pos-pos2;
        float dist = length(collision_axis);
        float rad_tot = rad_1*2;
        if (dist < rad_tot){
            vec2 n = collision_axis / (dist);
            float delta = (rad_tot - dist)*.5;
            update += delta*n*.75;
            n_col += 1;
        }
    }
    return itransform(pos+update);
}

vec2 solveCollision(vec2 pos){
    vec2 uv = (pos+1.)/2.;
    vec2 tiling = iResolution.xy/part_size*2.;
    vec2 idx = floor(uv*tiling)/tiling;
    vec2 tile_1 = uv;
    //vec2 tile_1 = texelFetch(TileIdx, ivec2(idx*iResolution), 0).xy;
    //pos = texture(TileIdx, tile_1 + vec2(.5)/tiling).xy;
    pos = transform(pos);

    float rad_1 = get_radius(gl_VertexID);
    int K = 2;

    int past_id[25] = int[25](-1,-1,-1,-1,-1,
                            -1,-1,-1,-1,-1,
                            -1,-1,-1,-1,-1,
                            -1,-1,-1,-1,-1,
                            -1,-1,-1,-1,-1);
    int indice = -1;
    vec2 update = vec2(0.);
    for (int i=-K; i<=K; i++){
        for(int j=-K; j<=K; j++){
            indice += 1;
            vec2 tmp = vec2(float(i), float(j));
            vec2 tile_2 = tile_1 + tmp/tiling;
            vec2 rnd = (hash22(pos))-.5;
            vec3 part_info = texelFetch(TileIdx, ivec2( (tile_2)*iResolution+rnd), 0).xyw;

            float idx_2 = part_info.z;
            if (idx_2 == -1) continue;
            if (idx_2 == gl_VertexID) continue;
            
            // Check if already fetch this particles
            bool a = false;
            for (int k=0; k<25; k++){
                if (past_id[k] == int(part_info.z)){
                    a = true;
                }
            }
            if (a) continue;
            past_id[indice] = int(part_info.z);
            vec2 pos2 = part_info.xy;
            pos2 = transform(pos2);
            vec2 collision_axis = pos-pos2;
            float dist = length(collision_axis);
            float rad_2 = get_radius(i);
            float rad_tot = rad_1 + rad_2;
            if (dist < rad_tot){
                vec2 n = collision_axis / (dist);
                float delta = (rad_tot - dist)*.5;
                update += delta*n*.3;
            }
        }
    }
    return itransform(pos+update);
}

void main(){

    vec2 pos = in_pos.xy;
    vec2 pos_last = in_pos.zw;

    float n_col = 0;
    vec2 new_pos = solveCollision3(pos, n_col);
    vec2 change = (new_pos-pos);
    //pos_last = pos_last + change*pow(.9, 1./(n_col+1));
    out_pos = vec4(new_pos, pos_last);
    out_col = in_col;
}
