#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;

uniform sampler2D iChannel0;
uniform float start_uy;
uniform float size;
uniform float offset_x;


void main()
{
    ivec2 uv = ivec2(gl_FragCoord.xy);
    
    int suy = int(start_uy);
    int s = int(size);
    int ox = int(offset_x);
    if (uv.y < suy){
       if (uv.y > (suy - s)){
            uv.y = suy;
            uv.x += ox;
       }
       else{
            uv.y = uv.y + s;
       }
    }
    vec4 col = texelFetch(iChannel0, uv, 0);
    fragColor = col;//*.0001  + vec4(size, start_uy, .0,.0);// + start_uy;
    //fragColor = vec4(vec2(uv.xy)/vec2(1920,1080), .0,.0) + .00001*col;

}
