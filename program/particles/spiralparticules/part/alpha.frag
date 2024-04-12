#version 330

in vec3 color;
in vec3 pos;
in float vel_int;
in float ID_out;

out vec4 outColor;

uniform mat4 modelview;
uniform mat4 projection;
uniform float iTime;

float hash11(float p){
    return fract(sin(p*12.789)*7896.4563);
}

float noise1(float p)
{
    float i = floor(p);
    float f = fract(p);
    return mix(hash11(i), hash11(i+1.), smoothstep(0., 1., f));
}
float flicker(float ID){
    float res = pow(noise1(ID+iTime*.001), 6.)*.98+.02;
    return res * 10.;
}

vec2 sphIntersect( in vec3 ro, in vec3 rd, in vec3 ce, float ra )
{
    vec3 oc = ro - ce;
    float b = dot( oc, rd );
    float c = dot( oc, oc ) - ra*ra;
    float h = b*b - c;
    if( h<0.0 ) return vec2(-1.0); // no intersection
    h = sqrt( h );
    return vec2( -b-h, -b+h );
}

vec4 getCol(vec2 p, float dist){
    p -= .5; 
    vec3 ro = vec3(0, 0, 3); // ray origin that represents camera position
    vec3 rd = normalize(vec3(p, -1)); // ray direction
    vec3 ce = vec3(0., 0., 1.);
    float ra = .9*dist; // Change size in fuction of pos coord in z axis
    vec2 sph = sphIntersect(ro, rd, ce, ra);

    if (sph.x>-.999 && vel_int>.2){
        float vint = clamp(vel_int, .0-iTime, 1.);
        vec3 col =  color * vint;

        float a = 1.;
        return vec4(col, a);
    }
    else{
        return vec4(0.);
    }
}

vec2 getDepth(){
    float far=gl_DepthRange.far; float near=gl_DepthRange.near;

    vec4 eye_space_pos = modelview * vec4(pos, 1.);
    vec4 clip_space_pos = projection * eye_space_pos;

    float ndc_depth = clip_space_pos.z / clip_space_pos.w;

    float depth = (((far-near) * ndc_depth) + near + far) / 2.0;
    return vec2(depth, length(eye_space_pos));
}

void main() {
    // Calculate the distance from the center of the point
    // gl_PointCoord is available when redering points. It's basically an uv coordinate.
    vec2 depth = getDepth();
    //vec4 color = getCol(gl_PointCoord.xy, sqrt(abs(pos.z+10))*.2+.2);
    vec4 col = getCol(gl_PointCoord.xy, 1./(1.+depth.y*.2)*1. + .2);

    // .. an use to render a circle!
    float ad = min(col.w, 1.);
    gl_FragDepth = depth.x*step(.0, ad) + (1-ad);

    float alpha = flicker(ID_out);
    col.rgb = vec3(alpha);
    col.r *= .0001;
    col.r = cos(ID_out/7500. * 2.*3.14159*10.)*.5+.5;
    col.r *= 8.;
    col.r = (alpha);
    col.b = ID_out/7500.;
    //outColor = vec4(color.rgb, max(color.r, max(color.g, color.b)));
    outColor = clamp(col, vec4(0.), vec4(4.));
}
