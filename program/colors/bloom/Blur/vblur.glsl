#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform vec2 iResolution;

uniform sampler2D iChannel0;
uniform float level;
uniform sampler2D Prev;

// REF : https://www.rastergrid.com/blog/2010/09/efficient-gaussian-blur-with-linear-sampling/


#define R iResolution

vec3 ColorFetch(vec2 coord)
{   
   if (level == -1.){
        vec4 col = textureLod(iChannel0, coord, level);
        col.a = clamp(col.a, 0., 100.);
        col.rgb = col.rgb*col.a;
        return col.rgb;//*smoothstep(.2, .4, length(col.rgb)); 
   }
   else{
        vec4 col = textureLod(iChannel0, coord, level);
        col.a = clamp(col.a, 0., 100.);//*smoothstep(.2, .4, length(col.rgb));
        vec4 prev_col = texture(Prev, coord);
        col.rgb = col.rgb*col.a + prev_col.rgb*.8; 
        return col.rgb;
   }
}


const float offset[3] = float[](0.0, 1.3846153846, 3.2307692308);
const float weight[3] = float[](0.2270270270, 0.3162162162, 0.0702702703);

void main()
{    
    vec2 uv = gl_FragCoord.xy / iResolution.xy;
    vec3 color = vec3(0.0);
    float weightSum = .0;

    //color += ColorFetch(uv);
    //weightSum += 1;
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
        //color += ColorFetch(uv + offset_ * vec2(1., .0))*W;// * weights[abs(i)];
        //color += ColorFetch(uv - offset_ * vec2(1., .0))*W;// * weights[abs(i)];
        //weightSum += 2.*W;
        float W = weight[i];
        color += ColorFetch(uv + offset[i]*vec2(1.,.0)/R.x)*W;
        color += ColorFetch(uv - offset[i]*vec2(1.,.0)/R.x)*W;
        weightSum += 2.*W;
    }//weights[i];}

    color /= weightSum;

    fragColor = vec4(color,1.0);
}
