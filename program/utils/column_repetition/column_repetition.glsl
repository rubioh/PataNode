#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;

uniform sampler2D iChannel0;
uniform float start_ux;
uniform float size;
uniform float offset_y;


void main()
{
    ivec2 uv = ivec2(gl_FragCoord.xy);
    
    int sux = int(start_ux);
    int s = int(size);
    int oy = int(offset_y);
    if (uv.x < sux){
       if (uv.x > (sux - s)){
            uv.x = sux;
            uv.y += oy;
       }
       else{
            uv.x = uv.x + s;
       }
    }
    vec4 col = texelFetch(iChannel0, uv, 0);
    fragColor = col;//*.0001  + vec4(size, start_uy, .0,.0);// + start_uy;
    //fragColor = vec4(vec2(uv.xy)/vec2(1920,1080), .0,.0) + .00001*col;

}
