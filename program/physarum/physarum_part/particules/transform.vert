#version 330 core

in vec4 in_infos;

out vec4 out_infos;

uniform sampler2D Trail;
uniform sampler2D SeedTex;
uniform float iFrame;
uniform vec2 iResolution;
uniform float part_size;
uniform float sensor_direction;
uniform float trail_thresh;
uniform float velocity_rate;
uniform float sensor_length;
uniform float update_direction;
uniform float to_center_amount;

#define R iResolution

float hash31(vec3 p){
    float k1 = dot(vec3(145.1244,117.4561, 157.45861)*.25, p);
    return fract(sin(k1*168.156787)*178.35412);
}

vec2 check_boundary(vec2 pos){
    vec2 new_pos = pos;
    float dy = pos.y;
    float dist = abs(dy);
    float radius = part_size/iResolution.y;
    if (dist > 1.-radius){ // TODO RADIUS IS APPROXIMATELY 0 SO....
        new_pos.y = pos.y - sign(dy)*(radius-(1.-dist));
        //TODO  CHANGE heading not the POS
            //heading = heading + PI; -> Rebond
    }

    float dx = pos.x;//*sign(pos.y);
    dist = abs(dx);
    radius = part_size/iResolution.x;
    if (dist > 1.-radius){ // TODO RADIUS IS APPROXIMATELY 0 SO....
        new_pos.x = pos.x - sign(dx)*(radius-(1.-dist));
        //TODO CHANGE heading not the POS
            //heading = heading + PI;
    }
    return new_pos;
}

mat2 rotation(float angle){
    return mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
}

vec2 transform(vec2 p){
    return (p+1.)*.5;
}


vec2 check_bound(vec2 p){
    if (p.x>1){
        p.x -= 2.;
    }
    if (p.x<-1){
        p.x += 2.;
    }
    if (p.y>1){
        p.y -= 2.;
    }
    if (p.y<-1){
        p.y += 2.;
    }
    return p;
}

vec3 get_sensor_information(vec2 pos, vec2 dir, float sl){
    float L = sensor_length; // Length of the sensor
    mat2 rot = rotation(sensor_direction);
    mat2 rot1 = rotation(-sensor_direction);

    vec2 front = transform(pos) + L * dir/R; // TODO R.x R.y R?
    vec2 left = transform(pos) + L * rot*dir/R;
    vec2 right = transform(pos) + L * rot1*dir/R;

    float info_front = (texture(Trail, front).x);
    float info_left = (texture(Trail, left).x);
    float info_right = (texture(Trail, right).x);

    vec3 info = vec3(info_front, info_left, info_right);
    return clamp(info, vec3(0.), vec3(trail_thresh));
}

float change_dir(vec3 info, float heading){
    float thresh = .0001;
    float angle = update_direction;
    if (info.x-info.y > thresh && info.x-info.z > thresh)
        return heading; // X>Y&Z
    if (info.y-info.x > thresh && info.z-info.x < thresh){
        float choose = floor(2.*hash31(info));
        if (choose == 0)
            return heading;
        return heading - angle;
    }
    if (info.y < info.z)
        return heading + angle;
    if (info.z < info.y)
        return heading;
    else
        return heading;
}

void main(){

    vec2 pos = in_infos.xy;
    float heading = in_infos.z; // Direction heading corresponds to cos(sensor_direction), sin(sensor_direction)
    vec2 dir = vec2(cos(heading), sin(heading));
    float sl = in_infos.w;

    if (iFrame < 1){
        int x = int(floor(gl_VertexID/iResolution.x));
        int y = int(mod(gl_VertexID, iResolution.x));
        ivec2 p = ivec2(x ,y);
        vec3 seed = texelFetch(SeedTex, p, 0).rgb;
        vec2 new_pos = vec2(seed.x, seed.y)*2-1;
        heading = -atan(new_pos.x, new_pos.y);
        out_infos = vec4(new_pos, heading, 0);
        return;
    }

    vec3 info = get_sensor_information(pos, dir, sl);
    heading = change_dir(info, heading);

    dir = vec2(cos(heading), sin(heading));

    vec2 pixel_size = 1./iResolution.xy*2; // TODO iResolution.xx ou iResolution.yy ou iResolution ?
    vec2 new_pos = pos + dir*velocity_rate*pixel_size;

    //TOWARD CENTER
    new_pos -= normalize(new_pos)/iResolution.xy * to_center_amount * pow(length(new_pos), 2.);

    // Boundary condition
    new_pos = check_boundary(new_pos)*.00001 + check_bound(new_pos);
    out_infos = vec4(new_pos, heading, info.x);
}
