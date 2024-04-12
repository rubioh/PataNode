#version 330

in vec4 in_position;
in vec4 prev_pos;

uniform mat4 projection;
uniform mat4 modelview;
uniform float iTime;
uniform float N_part;
uniform float next;
uniform float modNext;
uniform float angle;
uniform vec3 angle3;

out vec3 color;
out vec3 pos;
out float vel_int;
out float ID_out;

vec3 palette(float t){
    vec3 a = vec3(.5);
    vec3 b = vec3(.5);
    vec3 c = vec3(1.);
    vec3 d = vec3(.3,.2,.2);
    return a+b*cos(2.*3.14159*(c*t+d));
}

vec3 palette2(float t){
    vec3 a = vec3(.5);
    vec3 b = vec3(.5);
    vec3 c = vec3(1.);
    vec3 d = vec3(.8,.9,.3);
    return a+b*cos(2.*3.14159*(c*t+d));
}

mat2 rotate2D(float angle){
    return mat2(cos(angle), sin(angle), -sin(angle), cos(angle));
}

vec3 rotate(vec3 p){
    vec3 q = p;
    q.xz = rotate2D(angle)*q.xz;
    return q;
}

vec3 rotateXYZ(vec3 p){
    vec3 q = p;
    q.xz = rotate2D(angle3.x)*q.xz;
    q.yz = rotate2D(angle3.y)*q.yz;
    q.xy = rotate2D(angle3.z)*q.xy;
    return q;
}

void main() {
    vec3 tmp = in_position.yxz;
    tmp.x *= -1;
    vec3 p = rotate(tmp);
    p = rotateXYZ(tmp);

    //p.z += 2.5+2.5*cos(iTime*.01); 
    gl_Position = projection * modelview * vec4(p, 1.0);

    // Set the point size

    gl_PointSize = 20 + sin((iTime + gl_VertexID ) * 7.0) * 10.0*.2;

    // Calculate a random color based on the vertex index
    float ID = mod(gl_VertexID + sqrt(N_part+20)*floor(iTime*10.), N_part);
    ID = gl_VertexID;
    float goID = mod(gl_VertexID, modNext);
    float vel = length(in_position-prev_pos);
    color = (goID == 0.) ? palette(iTime*.001)*1. : palette2(vel*.1+(.7+iTime*.001));
    pos = p;
    vel_int = abs(in_position.w)+.001;
    ID_out = gl_VertexID;
}
