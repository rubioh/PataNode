# Session fades: eased transitions between states

## Problem

Live session mode switches states as a hard cut. The 2026-08-02 design put
"blended or interpolated transitions" out of scope: `SessionPlayer.goTo`
applies the incoming state's parameters and rewires every edge in one frame
(median 2.25 ms). In performance this reads as a jump — every parameter
snaps at once.

The goal is to make arriving at a state *ease in*: pick which parameters
should ease rather than snap, over a duration you choose.

## The lever

A GPU parameter in PataNode is not a number. It is a **string expression**
that `ProgramBase.getAdaptableEvaluationForUniform`
(`program/program_base.py:439`) `eval()`s every frame with `x` bound to the
base attribute, then `float()`s:

```python
try:
    modified_data = float(eval(evaluation))
except Exception:
    modified_data = x
```

So interpolation needs no new evaluation machinery and no extra render pull.
Writing `"(1-0.37)*(x*2)+(0.37)*(.9)"` into that slot *is* the fade — the
per-frame `bindUniformToProgram` picks it up on its own. Three consequences
the design leans on:

- An audio-driven expression (`"x*2"`) fades exactly like a literal
  (`".9"`). Numeric-only interpolation would have excluded the former,
  which is most of what this project actually binds.
- A malformed side degrades to a hard cut through the existing
  `except` fallback, rather than raising into the 60 Hz audio timer.
- An interrupted fade can nest: the live half-blended expression is itself
  a valid `old` side.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Where the config lives | On the **target state** (`state.fade`) | "When the session arrives here, ease these in." Survives reorder/insert, and works no matter which state you jumped from. |
| Interpolation | Synthesized `(1-a)*(old)+(a)*(new)`; real target string written at `a == 1` | See above. Both sides parenthesised — `old` is routinely compound. |
| Granularity | One duration + one curve per state | Covers the performance case: the whole scene arrives over N seconds. |
| Topology | Edges rewire at t=0, exactly as today | Zero risk to the existing switch path. A newly-connected branch still pops in; hide it by fading its blend parameter. |
| Interrupt | Seamless — the live expression becomes the next fade's `old` | No pop on Next. Nesting capped at `MAX_NESTING = 4`, past which the interrupted fade's clean target is used. |
| Param kinds | GPU uniforms only | CPU params are read as raw strings with no `eval` (`getSingleCpuParameters`), so a blend expression would reach the consumer as literal text. |
| Candidate list | **All** GPU uniforms of every node the *target* state carries, differing ones pre-ticked | A `Blend` node stores the same `baseBlend` in both states — only the wiring differs — and sweeping it is what makes the transition a crossfade. Listing only what differs would hide it. |
| Nodes the previous state lacks | Offered, outgoing side defaults to `"x"` | The node has a value to ease into, and the union model keeps it resident, so it has a live value to ease out of. Requiring it in both states meant an introduced node could only ever hard-cut. Prev-only nodes stay excluded — nothing to fade into. |
| Endpoint overrides | Per-param `from`/`to`, null = resolve at switch time | Null keeps a fade path-independent; explicit values are the Blend case. |

## File format

`state.fade` is optional. `SESSION_VERSION` stays **1** — bumping it would
make `LiveSession.from_dict` reject every `.pnlive` already on disk. The key
is omitted when absent, so an untouched session round-trips byte-identically
(verified against `saved/physarum_depth.pnlive`).

```json
"fade": {
  "duration": 2.0,
  "curve": "smoothstep",
  "params": [
    {"node_id": 140234, "program": "transform_program", "uniform": "sensor_length"},
    {"node_id": 140891, "program": "program", "uniform": "baseBlend", "from": "0", "to": "1"}
  ]
}
```

`program` is the key as it appears in `gpu_adaptable_parameters` — **not
always `"program"`**: a Physarum node's parameters live under
`"transform_program"`, and a node may own several.

## Architecture

`session/fade.py` is pure (no Qt, no GL, no scene), matching `model.py` /
`trigger.py` / `validation.py` / `propagation.py`. It holds `ease`,
`blend_expression`, `FadeParam`/`FadeSpec` (the document), `ResolvedFade`/
`ActiveFade` (the runtime), and `fade_candidates` — so the GUI does no
dict-walking of its own. `propagation._values` was promoted to
`values_for_kind` and reused for enumeration.

`SessionPlayer` gains the runtime. The load-bearing detail is **ordering
inside `goTo`**: `_apply_parameters` overwrites the values a fade needs to
start from, so the outgoing values are captured *before* it, live from the
nodes rather than from the previous state's dict. That is what makes a fade
independent of the path taken, and what makes an interruption seamless.

```
capture old (live)  →  _apply_parameters  →  _rewire  →  _start_fade (writes a=0)  →  _evaluate_once
```

The clock is anchored on the first `tick`, not at `goTo` — `self._now` is
only as fresh as the last audio tick, and is `0.0` before any has run;
anchoring there would make the first real tick see an elapsed time of
"since the epoch" and snap the fade shut. Same lazy-anchor reasoning as
`self._entry`. `_advance_fade` sits **before** `tick`'s `is_playing` guard,
because manual transport works while paused.

`finishFade()` is public and called before every serialize
(`onSessionCapture`, `onSessionOverwrite`, `onFileSave`/`onFileSaveAs`). A
synthesized blend expression reaching a saved file would be
indistinguishable from one the user typed, and would become the *target* of
every later fade — the same class of bug as commit 7ba3213.

`fade_candidates` substitutes `"x"` — `program_base.IDENTITY_EXPRESSION`, what
an unset uniform holds — only when the outgoing value is *absent* (missing node
or missing uniform), never when it is present but blank; a blanked expression is
malformed and stays dropped. The substitute is flagged `from_missing` so the
editor can show the node's real live value instead, read through
`session.player.read_live_param`. That is display only: an untouched endpoint
still persists as `null` and resolves live at switch time, so these fades stay
path-independent like every other. `differs` keeps the pre-tick honest by
itself — an introduced node's untouched uniforms sit at `"x"` on both sides, so
a node arriving with 20 defaults pre-ticks none of them.

`gui/widgets/fade_window.py` is a top-level `QWidget` following
`PalettePreviewWindow`: created lazily by the dock, then shown/hidden, never
rebuilt. No refresh timer — it is an editor, not a live view. Only nodes
with something ticked start expanded: a real state pair in
`saved/physarum_depth.pnlive` is 22 nodes and 125 parameters with **3**
differing, and expanding all of it buries the rows worth looking at.

At that size a row is hard to tie back to a node on the canvas, so hovering one
outlines its node in the graph. It drives `QDMGraphicsNode.hovered`
(`nodeeditor/node_graphics_node.py:257`) rather than inventing a second
highlight, so pointing at a row reads exactly like pointing at the node. Node
rows carry the same `node_id` role as their parameter rows, so either resolves
the same way. Cleared on viewport `Leave`, on hide, on close, and on `setTarget`
— repopulating invalidates every id. The whole path is `getattr`-guarded: the
window can be pointed at a player before a scene exists, and a hover must never
raise.

## Verification

`tests/session/test_fade.py`, `test_player_fade.py`, `test_fade_window.py`,
plus fade cases in `test_validation.py` — 389 tests pass.

Verified end to end against `saved/physarum_depth.pnlive` on 22 real
`ShaderNode`s with compiled GLSL and a standalone GL context: the three
differing parameters held their outgoing values at t=0, interpolated
exactly (`1200 → 2000` reading 1400 at 25%, 1600 at 50%), landed on the
exact target strings, and an interrupting `goTo` was numerically continuous
across the switch at nesting depth 1.

## Not built

- Fading edge topology. Edges still cut at t=0.
- Per-parameter durations or curves.
- Timed/keyframed parameter animation outside a state transition.
- CPU parameters.
