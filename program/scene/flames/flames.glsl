#version 330 core
layout (location=0) out vec4 fragColor;

uniform float iTime;
uniform float freq;
uniform float strength;
uniform float anim;
uniform vec2 iResolution;

/*
 * Fast FBM Fire
 * Copyright (C) 2023 NR4 <nr4@z10.info>
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
 
const vec3 c = vec3(1, 0, -1);
const mat2 m = .4 * mat2(4, 3, -3, 4);

// Created by David Hoskins and licensed under MIT.
// See https://www.shadertoy.com/view/4djSRW.
float hash12(vec2 p)
{
	vec3 p3  = fract(vec3(p.xyx) * .1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract(dot(p3.xy, p3.zz));
}

float lfnoise(vec2 t)
{
    vec2 i = floor(t);
    t = c.xx * smoothstep(0., 1., fract(t));
    vec2 v1 = 2. * mix(vec2(hash12(i), hash12(i + c.xy)), vec2(hash12(i + c.yx), hash12(i + c.xx)), t.y) - 1.;
    return mix(v1.x, v1.y, t.x);
}

float fbm(vec2 uv)
{
    vec2 uv0 = uv;
    uv = uv * freq * vec2(5., 2.) - vec2(-2., -.25) - 3.1 * iTime * c.yx;
	float f = 1.,
        a = .5,
        c = 2.5;
	
    for(int i = 0; i < 5; ++i) {
        uv.x -= .15 * clamp(1. - pow(uv0.y, 4.), 0., 1.) * lfnoise(c * (uv + float(i) * .612 + iTime));
        c *= 2.;
        f += a * lfnoise(uv + float(i) * .415);
        a /= 2.;
        uv *= m;
    }
    return f / 2.;
}

void main( )
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;
    float anim = smoothstep(0., 1., 1.-uv.y + anim );
    fragColor = vec4(clamp(1.5 * pow(clamp(pow(fbm(uv),  strength * 1. + 4. * clamp(uv.y * uv.y, .0, 1.)) * 1.5, 0., 1.) * c.xxx, vec3(1, 3, 6)), 0., 1.) * anim, 1.);
}
