#version 330 core
layout (location=0) out vec4 fragColor;

uniform vec2 iResolution;
uniform sampler2D input_texture;
uniform sampler2D history;
uniform float smooth_rate;
uniform float hold_frames;

// Parser constraint, and it bites twice: ProgramsUniforms splits this file on
// ";" and, for every chunk containing the declaration keyword, registers that
// chunk's third word as a shader input. So comments must sit below all the
// declarations above -- and must also avoid the keyword itself, because the
// trailing chunk includes this whole block. Prose mentioning it registers a
// phantom entry that ends up in saved scene files.
// tests/depth/test_depth_smooth.py pins the parsed set, so a slip fails there
// rather than silently corrupting a save.
//
// Input is a depth image as Depth Input produces it: normalised depth in rgb,
// validity in a. Two things flicker on a real sensor -- the depth values
// themselves, and whether a pixel is measured at all. The exponential average
// handles the first; holding the last valid depth handles the second, which is
// the one that pops hardest because a pixel jumps between opaque and
// transparent.
//
// history is the previous frame's output, so alpha carries freshness rather
// than raw validity: 1.0 when last measured, decaying while a pixel stays
// unmeasured. That makes a hole fade out over hold_frames instead of
// reappearing instantly, and downstream still reads alpha as validity.

void main()
{
    vec2 uv = gl_FragCoord.xy / iResolution.xy;

    vec4 cur = texture(input_texture, uv);
    vec4 prev = texture(history, uv);

    float rate = clamp(smooth_rate, 0.0, 1.0);
    float decay = 1.0 / max(hold_frames, 1.0);

    vec3 depth;
    float freshness;

    if (cur.a > 0.0) {
        // No history means the first frame after the buffers were cleared, or
        // a pixel measured for the first time. Adopt the measurement outright:
        // fading in from an empty buffer would darken every new surface for
        // several frames.
        depth = prev.a > 0.0 ? mix(prev.rgb, cur.rgb, rate) : cur.rgb;
        freshness = 1.0;
    } else {
        depth = prev.rgb;
        freshness = max(prev.a - decay, 0.0);
    }

    // NaN would be absorbing: mix() propagates it and the hold branch above
    // preserves it, so one bad input frame would poison the pixel for the
    // lifetime of the buffers. Depth Input cannot produce one (its divide is
    // guarded and its result clamped), but this program accepts any
    // depth-shaped image, so recover instead of latching.
    if (any(isnan(depth))) {
        depth = cur.rgb;
    }

    fragColor = vec4(depth, freshness);
}
