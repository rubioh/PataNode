#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D FlowTex;

void main()
{
    vec2 uv = gl_FragCoord.xy/iResolution;
    vec2 px = 1./iResolution;

    vec4 c = texture(FlowTex, uv);

    // Confidence-weighted Jacobi step. Trustworthy vectors bleed into flat
    // neighbourhoods; unconstrained ones contribute nothing and get overwritten.
    vec2 sum = c.xy*c.a*2.;
    float wsum = c.a*2.;
    float conf = c.a*2.;

    for (int k = 0; k < 4; k++){
        vec2 o = k == 0 ? vec2(1., 0.)
               : k == 1 ? vec2(-1., 0.)
               : k == 2 ? vec2(0., 1.)
               :          vec2(0., -1.);

        vec4 n = texture(FlowTex, uv + o*px);
        sum += n.xy*n.a;
        wsum += n.a;
        conf += n.a;
    }

    vec2 flow = wsum > 1e-5 ? sum/wsum : vec2(0.);

    // Confidence diffuses alongside the vectors, so each iteration widens the
    // region that carries a usable estimate by one pixel.
    fragColor = vec4(flow, 0., conf/6.);
}
