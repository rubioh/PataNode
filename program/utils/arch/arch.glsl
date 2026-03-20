#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform float input_x;
uniform float input_y;
uniform float offset_x;
uniform float offset_y;
uniform float pan_y;
uniform float scale;
uniform sampler2D iChannel0;
float msign(in float x) { return (x<0.0)?-1.0:1.0; }

float cos_acos_3( float x ) { x=sqrt(0.5+0.5*x); return x*(x*(x*(x*-0.008972+0.039071)-0.107074)+0.576975)+0.5; } // https://www.shadertoy.com/view/WltSD7

float sdEllipse( vec2 p, in vec2 ab )
{
  //if( ab.x==ab.y ) return length(p)-ab.x;

	p = abs( p ); 
    if( p.x>p.y ){ p=p.yx; ab=ab.yx; }
	
	float l = ab.y*ab.y - ab.x*ab.x;
    float m = ab.x*p.x/l; float m2 = m*m;
	float n = ab.y*p.y/l; float n2 = n*n;
    float c = (m2+n2-1.0)/3.0; float c2 = c*c; float c3 = c*c2;
    float d = c3 + m2*n2;
    float q = d  + m2*n2;
    float g = m  + m *n2;

    float co;

    if( d<0.0 )
    {
        float h = acos(q/c3)/3.0;
        float s = cos(h); s += 2.0;
        float t = sin(h); t *= sqrt(3.0);
        float rx = sqrt( m2-c*(s+t) );
        float ry = sqrt( m2-c*(s-t) );
        co = ry + sign(l)*rx + abs(g)/(rx*ry);
    }
    else                                    // d>0
    {                                       // q>0
        float h = 2.0*m*n*sqrt(d);          // h>0
        float s = pow(q+h, 1.0/3.0 );       // s>0
        float t = c2/s;                     // t>0
        float rx = -(s+t) - c*4.0 + 2.0*m2;
        float ry =  (s-t)*sqrt(3.0);
        float rm = sqrt( rx*rx + ry*ry );
        co = ry/sqrt(rm-rx) + 2.0*g/rm;
    }
    co = (co-m)/2.0;

    float si = sqrt( max(1.0-co*co,0.0) );
 
    vec2 r = ab * vec2(co,si);
	
    return length(r-p) * msign(p.y-r.y);
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = ( 2.*gl_FragCoord.xy - iResolution.xy ) / iResolution.y;
    uv += vec2(offset_x, offset_y);
    uv *= scale;
    float c = sdEllipse(uv, vec2(input_x, input_y));
    vec3 col = texture(iChannel0, uv).rgb;
    //c = step(0, c);
//    col *= step(c, 0.);
if (uv.y > pan_y) {
col *= step(c, 0);
}
    fragColor = vec4(col,c);
}
