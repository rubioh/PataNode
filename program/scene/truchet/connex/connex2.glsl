uniform float iFrame;
uniform sampler2D iChannel0;


float N = 30.; // vertical number of tiles

vec2 hash( vec2 p )
{
    //p = mod(p, 4.0); // tile
    p = vec2(dot(p,vec2(175.1,311.7)),
             dot(p,vec2(260.5,752.3)));
    return fract(sin(p+455.)*18.5453);
}

#define R    iResolution.xy
#define T(U) texelFetch( iChannel0, ivec2(U), 0 )
#define H(p)  hash(p).x

void main()
{
    vec2 u = gl_FragCoord.xy;
    if ( iFrame < 1) {         // --- init: create truchet
        vec2 I = u-.5;                        // store truchet data
        fragColor.w = step(.5,H(I));                  // random axis
     // if (u.x > N*R.x/R.y || u.y > N) { fragColor.yz = vec2(0); return; }
        fragColor.y = 1.+I.x+10.*I.y;               // id of tile segment #1
        fragColor.z = -fragColor.y;                           // id of tile segment #2
        return;
    }
    
    u -= .5;
    fragColor = T(u);                                 // previous state
    if (u.x > N*R.x/R.y || u.y > N) return;   // propagate only visible tiles
    
                                              // --- propagate id along connections
#define left(T)    T.y
#define right(T)   T.z
#define bot(T)   ( T.w<1. ? T.y : T.z )
#define top(T)   ( T.w<1. ? T.z : T.y )
    if (fragColor.w<1.) { // tile contains:  \     new id = min(connections)
        fragColor.y = min( fragColor.y, min( right(T(u-vec2(1,0))), top(T(u-vec2(0,1))) ));
        fragColor.z = min( fragColor.z, min( left (T(u+vec2(1,0))), bot(T(u+vec2(0,1))) ));
    }
    else {        // tile contains:  /     new id = min(connections)
        fragColor.y = min( fragColor.y, min( right(T(u-vec2(1,0))), bot(T(u+vec2(0,1))) ));
        fragColor.z = min( fragColor.z, min( left (T(u+vec2(1,0))), top(T(u-vec2(0,1))) ));
    }
} 
