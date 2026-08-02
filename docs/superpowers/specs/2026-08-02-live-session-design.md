# Live Session — Design

**Date:** 2026-08-02
**Status:** Approved, ready for implementation planning

## Problem

PataNode saves a graph as a single snapshot. A performance is not a single graph — it is a sequence of graph states that build on each other over the course of a set.

Today the only way to perform that sequence is to build the graph by hand, live, in front of an audience. There is no way to prepare a set as an ordered series of states and replay it.

A **live session** is an ordered list of graph states, saved as one file, replayed one after another. You author it by capturing the graph as you build it up; you perform it by advancing through the states, driven manually or by audio.

## Scope

**In scope:** authoring a session (capture, edit, reorder, propagate), replaying it (manual and audio triggers), and the file format.

**Out of scope:** blended/interpolated transitions between states, timed hands-free playback, multi-window sessions, editing one state while a different state stays on the output.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Transition style | **Hard cut** | Predictable, matches how graph diffing already works. Blending is a later feature, not a prerequisite |
| Trigger | **Manual + audio, stored per state** | State 3 can wait for you, state 4 for a kick. Timed playback deliberately excluded (YAGNI) |
| Shader compilation | **All precompiled at session load** | Compiling mid-set hitches the output. Load time is prep time |
| Editing a captured state | **Edit-and-propagate**, opt-in per overwrite | Makes a 30-state session maintainable. Automatic propagation is too dangerous |
| Editing vs. output | **Single scene; output follows the editor** | A third of the work of dual-scene, and matches how the app works today |
| Validation failures | **Blocking banner at load, with "Run anyway" + persistent markers** | The tool must never be able to stop a set, but must never surprise you either |

## Architecture

### Why the union-scene model

Two facts about the existing codebase determine the design:

1. **GL programs are owned by node instances and are never cached.** `ProgramBase.loadProgramToCtx` calls `ctx.program(...)` on every construction (`program/program_base.py:151`). "Precompile everything" therefore necessarily means "keep the node instances alive."
2. **Rendering is a single pull from the Screen node.** `PataNodeSubWindow.render` calls `self.screen_node.render(...)` (`gui/subwindow.py:81`), which walks upstream via `evalInputNodes`. A node not reachable from the Screen node is never evaluated and costs nothing per frame.

Together these mean: **instantiate every node the session will ever use, once, at load. A state is then defined by edge topology and parameter values, not by which nodes exist.** Nodes outside the current state sit disconnected and free.

**The most important consequence, and the easiest thing to get wrong when implementing this:** a state's stored `nodes` list is used for exactly two things — contributing to the union at load, and supplying parameter values on entry. It does **not** drive instantiation or removal at runtime. A node present in the union but absent from state *i*'s node list is neither destroyed nor reset; it simply keeps its current parameters and, having no edges in state *i*, goes unreachable from the Screen node and stops rendering. This is the specific behaviour that separates the union model from `Scene.deserialize`'s normal reuse-and-remove semantics.

This maps directly onto "the graph grows little by little" — growth is the edge set expanding to reach nodes that were already warm.

### Rejected alternatives

- **Full snapshot replay** (`scene.deserialize(snapshot)` per state, reusing the undo/redo engine). Nearly free to build, but `Scene.deserialize` removes nodes absent from the snapshot (`nodeeditor/node_scene.py:450-452`) and rebuilds them on return — a GLSL compile mid-set. Suppressing removal converges on the union model anyway.
- **One prebuilt Scene per state.** Zero transition cost, but 30 states × 15 nodes is ~450 resident GL programs plus FBOs, and duplicating every node per state makes propagation harder rather than easier.

## Data model

A state is a **normal scene snapshot plus a name and a trigger**. No second schema.

```json
{
  "version": 1,
  "name": "fabulaignes set",
  "states": [
    {
      "name": "intro",
      "trigger": {"type": "manual"},
      "scene": { "id": 140440983657040, "scene_width": 64000,
                 "scene_height": 64000,
                 "nodes": ["… standard node dicts …"],
                 "edges": ["… standard edge dicts …"] }
    },
    {
      "name": "build",
      "trigger": {"type": "audio", "feature": "kick_count", "count": 8},
      "scene": { "…": "…" }
    }
  ]
}
```

`"scene"` is exactly what `Scene.serialize()` produces. Consequences:

- Every state remains independently loadable as a plain `.pn`.
- Existing node/edge/socket deserialization applies unchanged.
- The session layer requires **no changes to `nodeeditor/`**.

**The union is derived, not stored.** At load, merge every state's node list by `id`. Nothing to keep in sync; adding a node to state 7 automatically enlarges the union.

**`"version": 1` from day one.** The scene format has no version field, and six files in `saved/` silently load with every parameter reset to defaults as a result. Not repeating that in a new format.

**Node dicts repeat across states.** A 30-state session stores each node ~30 times. Accepted: it keeps each state self-contained and independently debuggable, and these files are small. A delta chain would mean corrupting state 3 breaks 4 through 30.

File extension `.pnlive`, stored in `saved/`.

### Trigger forms

| Form | Meaning |
|---|---|
| `{"type": "manual"}` | Waits for you. Never auto-advances |
| `{"type": "audio", "feature": "kick_count", "count": 8}` | Snapshot the counter on entry; advance when it has moved by `count` |
| `{"type": "audio", "feature": "low_slow", "above": 0.7, "hold": 2.0}` | Advance when a continuous feature stays above `above` for `hold` seconds |

Counter-delta uses the **monotonic counters** rather than the `on_kick`-style single-frame pulses, so a dropped frame cannot desync the count. The counters that actually exist are `kick_count`, `hat_count` and `snare_count` (`audio/audio_event.py:50-58`) — those three only.

The `on_tempo*` family is **not** usable for counter-delta triggers: they are phase values ("one turn in 4 kick", `audio/audio_bpm.py:40-53`), not counters. Bar-aligned advancing is expressed as `kick_count` with a multiple (e.g. 32 kicks) rather than through `on_tempo8`. Threshold-form triggers may still name any continuous feature, `on_tempo*` included.

Validation rejects a counter-delta trigger naming anything other than the three real counters.

## Components

Four units, each with one purpose and a testable boundary.

| Unit | Responsibility | Depends on |
|---|---|---|
| `LiveSession` | Parse/serialize `.pnlive`, hold ordered states, atomic save | stdlib only |
| `SessionState` | Name + scene dict + trigger | stdlib only |
| `Trigger` | Pure predicate: `(features, entry_snapshot, elapsed) -> bool` | stdlib only |
| `SessionPlayer` | Owns target scene; load, `goTo`, next/prev, trigger evaluation | `Scene`, `Node`, `Edge` |

Only `SessionPlayer` touches Qt or the scene. The other three are pure data and logic.

## Data flow

### Session load

1. Parse file; reject unknown `version` outright.
2. Merge all states' node lists by `id` → the union.
3. Deserialize `{nodes: union, edges: []}` into the scene. **This is where every GLSL program compiles.** Nothing is wired yet.
4. Run the validation pass (below); show the banner if it found anything.
5. `goTo(0)`.

Step 3 is the slow step and happens during setup, not during the set.

### Advancing to state *i*

1. **Apply parameters** — for each node in the state, find the live instance by `id` and call `node.deserialize(data, restore_window_size=False)`.

   `restore_window_size=False` is load-bearing. Without it, `changeWindowSize` fires `reload_program()` (`node/shader_node_base.py:154-156`), recompiling the shader — precisely the hitch the design exists to avoid.

   The same call is safe for non-shader nodes: `Node.deserialize` takes `**kwargs` (`nodeeditor/node_node.py:618`), so plain nodes silently ignore the flag while `ShaderNode` honours it. This is why the feature needs no signature change in `nodeeditor/`, and why integration tests can use plain `Node`s.

2. **Rewire edges** — drop the scene's current edges, build the state's. Edge construction touches no GL, so this is microseconds. Rebuilt wholesale rather than diffed: simpler, and the cost is irrelevant.

3. **Re-evaluate once** — mark the Screen node dirty, pull a single render.

Evaluation is **suppressed during steps 1–2**. Edge assignment fires `onInputChanged` per socket (`nodeeditor/node_edge.py:300`), so a naive rewire triggers a cascade of re-evaluations mid-transition. One `doEvalOutputs()` at the end instead.

**Transitions are all-or-nothing.** `goTo` applies to a staging structure, validates, and only then commits to the live scene. A transition that fails leaves the scene untouched on the current state.

`goTo(i)` is idempotent and is the single implementation behind next, previous, and jump-to-state.

### Trigger evaluation

Hooked into the existing 60 Hz audio timer, immediately after `set_audio_features()` (`app.py:119`), which already computes every feature needed. If the player is playing and the current state's trigger fires, advance.

**Manual "next" always works**, regardless of what the current state is waiting on. You cannot be stuck in front of an audience because a kick did not land.

## Authoring

**Capture** appends the current graph as a new state after the current one. **Overwrite** replaces the current state. Plus insert, delete, reorder, rename.

Jumping to a state loads it into the scene and **pauses playback** — you cannot be auto-advanced out of a state you are editing.

### Propagation

When you jump to state *i*, the player retains that state's scene dict as a **baseline**. On overwrite, it diffs baseline against the current graph, producing a change list at parameter granularity — a parameter being `(node_id, cpu|gpu, program, uniform)`, exactly how `ShaderNode.serialize` already lays them out (`node/shader_node_base.py:464-497`). Node and edge additions/removals come from the same diff.

Propagation then walks states *i+1…N*, applying each change **conditionally**:

- **Parameter changed old → new:** if the state still holds `old`, set it to `new`. If it holds anything else, **skip** — that value was deliberately changed downstream and clobbering it would destroy work.
- **Node added:** ensure present in later states (same `id`). Usually already true.
- **Node or edge removed:** remove from later states — **unless that state built on it**, in which case skip and report, exactly as for a diverged parameter.

  "Built on it" means the later state has an edge touching the removed node that the edited state did not have. Concretely: you add a Bloom node in state 3, wire it into Mapping by state 6, then go back and delete it from state 3. State 6 keeps its Bloom and appears in the skipped list; states 4 and 5, which only inherited it untouched, lose it.

  Without this rule, deleting a node silently destroys later wiring while the *parameter* rule right above it carefully protects a tweaked slider — an asymmetry that would lose real work and only surface mid-set.

The skip rule is the safety property, and it is not silent. Overwrite shows a summary before committing:

```
Applying 4 changes to states 4–7.
  • 3 will be applied
  • 1 skipped — Blur.radius in state 6 was changed independently
                (0.8, expected 0.35)
```

Options: apply, apply-anyway, cancel. **Propagation is opt-in per overwrite**, never automatic — some fixes belong only to one state.

### Deliberate limits

- **No session-level undo.** The session lives in memory until explicitly saved; a bad propagation is recovered by not saving.
- **Propagation only moves forward.** Editing state 3 never touches 1–2; backward propagation has no coherent meaning when the graph grows monotonically.

## UI

Follows the existing dock pattern (`gui/patanode.py:668-683`).

- **`Live Session` dock**, bottom area — the state list: index, name, trigger summary, currently-playing marker, and a persistent warning marker on any state with an unresolved validation problem. Click to jump, drag to reorder.
- **`&Session` menu**, alongside `&Window` and `&Map` (`gui/patanode.py:569-581`) — New / Open / Save / Save As, Capture State, Overwrite State, Delete State.
- **Transport** — Play / Pause / Next / Previous in the dock, bound to keys and reachable from the existing MIDI controller layer (`controller/`).

The session targets **one subwindow**, the active `PataNodeSubWindow` when the session is opened. Multi-window sessions are not meaningful with a single GL context and one Screen node driving output.

### Integration points

Three, all additive; no existing behaviour changes:

1. `app.py:119` — one call after `set_audio_features()` for trigger evaluation.
2. `gui/patanode.py` — dock and menu construction.
3. `SessionPlayer` holds the target subwindow's `scene`; everything else uses existing `Scene`/`Node`/`Edge` APIs.

## Error handling

**Governing rule: no modal dialogs during playback.** Anything that fails while a session is running reports to the status bar and a session log. Modals are acceptable at load and while authoring; never in front of an audience.

### One validation pass at load

All problems collected in a single pass and surfaced together in a blocking banner, each identified by state index and node:

| Failure | Behaviour |
|---|---|
| Node fails to instantiate (unregistered op_code, GLSL compile error) | Banner |
| A state's edge references a missing socket | Banner |
| Trigger names a feature not in `list_audio_features` | Banner |
| Malformed or unknown `version` | Refuse to open entirely — no partial load |

**Playback will not start while the banner is unacknowledged.** Two choices:

- **Fix and reload** — repair the session, reload it.
- **Run anyway** — play degraded: failed nodes absent, broken edges dropped, bad triggers downgraded to manual.

`Run anyway` exists because for a live performance tool, refusing to run is a worse failure than running imperfectly — the tool must not be able to stop a set. To keep it from becoming a reflex, **the affected states keep a persistent warning marker in the dock for the whole session**; dismissing the banner does not clear it.

### Runtime failures

`goTo(i)` raising mid-set leaves the current state intact, logs, and keeps rendering. Guaranteed by the staging-then-commit structure.

### Session save

Reuses the atomic write pattern now in `Scene.saveToFile`: serialize fully, write to a temp file, `fsync`, `os.replace`. A session represents hours of work and must never be truncated by a failed save.

## Testing

The design deliberately concentrates the interesting logic in pure functions.

**Unit — no Qt, no GL:**

- `Trigger` — counter-delta arithmetic, threshold-with-hold timing, unknown feature, manual never firing, and **counter reset**: if the audio engine restarts, `kick_count` drops back to 0 and the entry-snapshot delta goes negative. Treat a negative delta as a reset and re-snapshot rather than advancing or hanging.
- **Propagation** — applies when values match; **skips when they diverge** (the safety property, tested explicitly); node add/remove; forward-only.
- `LiveSession` — parse/serialize round-trip, version rejection, malformed input, atomic-save-preserves-original.
- **Validation pass** — each failure category detected and reported with its state index; a clean session produces no findings.
- **Union computation** — overlapping node sets across states, exactly one instance per `id`.

**Integration — `QApplication`, plain `Node`/`Edge`, no GL context**, following the fixtures in `tests/serialization/conftest.py`:

- `SessionPlayer.goTo` — edge rewiring correctness, idempotency of repeated `goTo(i)`, and that a failing transition leaves the scene untouched.
- Capture → overwrite → propagate round-trip through a multi-state session.

**Manual verification, required before trusting it live:**

- GLSL compile cost at session load for a realistic union (target: report it, so the user knows what to expect).
- Transitions are genuinely hitch-free with real shader nodes — measure transition time and confirm no dropped frames.

These two cannot be unit-tested and are the design's main technical risk.

## Open questions

None blocking. Deferred by choice: blended transitions, timed playback, dual-scene editing, multi-window sessions.
