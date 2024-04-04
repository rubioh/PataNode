#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform sampler2D iChannel0;

// REF : https://www.rastergrid.com/blog/2010/09/efficient-gaussian-blur-with-linear-sampling/

#define R iResolution

vec3 ColorFetch(vec2 coord)
{
 	return texture(iChannel0, coord).rgb;   
}

const float offset[3] = float[](0.0, 1.3846153846, 3.2307692308);
const float weight[3] = float[](0.2270270270, 0.3162162162, 0.0702702703);

void main()
{    
    
    vec2 uv = gl_FragCoord.xy / iResolution.xy;
    
    vec3 color = vec3(0.0);
    float weightSum = 0.0;


    color += ColorFetch(uv)*weight[0];
    weightSum += weight[0];
    for (int i = 1 ; i<3 ; i++){
        vec2 offset_ = vec2(float(i))/iResolution.xy;
        //if (offset_.x+uv.x<0 || offset_.x+uv.x>1){
        //    continue;
        //}
        //if (offset_.y+uv.y<0 || offset_.y+uv.y>1){
        //    continue;
        //}
        //float W = exp(-float(i*i)*.4);
        //color += ColorFetch(uv + offset_ * vec2(0., 1.))*W;// * weights[abs(i)];
        //color += ColorFetch(uv - offset_ * vec2(0., 1.))*W;// * weights[abs(i)];
        float W = weight[i];
        color += ColorFetch(uv + offset[i]*vec2(0.,1.)/R.y)*W;
        color += ColorFetch(uv - offset[i]*vec2(0.,1.)/R.y)*W;
        weightSum += 2.*W;
    }//weights[i];}

    color /= weightSum;

    fragColor = vec4(color,1.0);
}
