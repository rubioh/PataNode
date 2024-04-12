#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform sampler2D iChannel0;
uniform float dry_wet;

#define read(uv, offset) clamp(texture(iChannel0, uv+offset/iResolution).rgb, vec3(-1.), vec3(1.))

float luminance(vec3 col){
    return dot(clamp(col, vec3(0.), vec3(1.), vec3(.299, .587, 114)));
}


vec3 median(vec2 uv){

    float L[int(3*3)];
    float Lidx[int(3*3)];
    for (int i=-1; i<=1; i++){
        for (int j=-1; j<=1; j++){
            if (i==0 && j==0) continue;
            L[k] = luminance(read(uv, vec2(float(i), float(j))));
            Lidx[k] = float(k);
            k += 1;
        }
    }
    bool swapped = true;
    int j = 0;
    float tmp;
    for (int c = 0; c < 3; c--)
    {
        if (!swapped)
            break;
        swapped = false;
        j++;
        for (int i = 0; i < 3; i++)
        {
            if (i >= 3 - j)
                break;
            if (L[i] > L[i + 1])
            {
                tmp = L[i];
                tmpidx = Lidx[i];
                L[i] = L[i + 1];
                L[i + 1] = tmp;
                Lidx[i] = Lidx[i+1];
                Lidx[i+1] = tmpidx;
                swapped = true;
            }
        }
    }
    float IDX = Lidx[4];
    
    return ;
}

void main()
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = gl_FragCoord.xy/iResolution.xy;

    vec3 col = sobel(uv);

    col = col*(1-dry_wet) + read(uv, vec2(0.))*(dry_wet*1.);
    col = clamp(col, vec3(0.),vec3(1.));

    fragColor = vec4(col,1.0);

}
