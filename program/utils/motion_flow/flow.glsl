#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D CurrLuma;
uniform sampler2D PrevLuma;
uniform float lambda_reg;

#define CURR(o) texture(CurrLuma, uv + (o)*px).r
#define PREV(o) texture(PrevLuma, uv + (o)*px).r

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution;
    vec2 px = 1./iResolution;

    // Accumulate the Lucas-Kanade normal equations over a gaussian-weighted 5x5
    // window: spatial gradients from this frame, temporal gradient against the last.
    float Ixx = 0., Iyy = 0., Ixy = 0., Ixt = 0., Iyt = 0.;

    for (int j = -2; j <= 2; j++){
        for (int i = -2; i <= 2; i++){
            vec2 o = vec2(i, j);
            float w = exp(-dot(o, o)/4.);

            float Ix = .5*(CURR(o + vec2(1., 0.)) - CURR(o - vec2(1., 0.)));
            float Iy = .5*(CURR(o + vec2(0., 1.)) - CURR(o - vec2(0., 1.)));
            float It = CURR(o) - PREV(o);

            Ixx += w*Ix*Ix;
            Iyy += w*Iy*Iy;
            Ixy += w*Ix*Iy;
            Ixt += w*Ix*It;
            Iyt += w*Iy*It;
        }
    }

    // Solve M*v = -b with damping on the diagonal. Without it a flat window gives a
    // singular matrix and the flow explodes instead of reading zero.
    //
    // The damping is proportional to the gradient energy, not absolute: a fixed
    // lambda would mean a dim input gets crushed to zero while a high-contrast one
    // passes through untouched. The epsilon is only there to keep flat regions finite.
    float trace = Ixx + Iyy;
    float reg = lambda_reg*trace + 1e-7;

    float a = Ixx + reg;
    float d = Iyy + reg;
    float det = a*d - Ixy*Ixy;

    vec2 flow = vec2(0.);

    if (abs(det) > 1e-12){
        flow = -vec2(d*Ixt - Ixy*Iyt, a*Iyt - Ixy*Ixt)/det;
    }

    // Harris-style cornerness, normalised by trace^2 so it stays a 0..1 reading
    // independent of contrast. Peaks at .25 for an ideal corner, hence the *4.
    // Low along an untextured edge, where the aperture problem means only one
    // component of the vector is actually constrained.
    float confidence = clamp(4.*(Ixx*Iyy - Ixy*Ixy)/(trace*trace + 1e-12), 0., 1.);

    // Hand downstream passes UV units per frame, so the field stays meaningful
    // whatever resolution it was computed at.
    fragColor = vec4(flow*px, 0., confidence);
}
