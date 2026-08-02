# Live Session — Verification Results

**Branch:** `feat/live-session`
**Date:** 2026-08-02
**Status:** automated portion complete; manual portion outstanding (needs the GUI and human eyes)

## What this document is for

The design rests on one claim that no unit test can prove: **a state transition compiles nothing, so the projected output does not hitch mid-set.** Everything else in the feature is covered by the 169 automated tests on this branch. This is the record of what was measured instead.

## Automated results

Harness: `tools/measure_session_cost.py`

Run with:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python tools/measure_session_cost.py
```

> **These numbers are not yet trustworthy.** They were taken before the final
> whole-branch review found that `_rewire` called `edge.remove()` without
> `silent=True`, so every removed edge fired `onInputChanged` and, on a real
> `ShaderNode`, a full upstream render pull — N cascading evaluations per
> transition rather than one. The harness could not see it because it uses plain
> `Node`, whose `onInputChanged` only marks dirty. That is now fixed
> (`session/player.py`), but the figures below were measured on the old path and
> on plain nodes either way. **Step 3 of the manual checklist is what actually
> settles this.**

### Transition cost — 40 nodes, 30 states, plain `Node`, no GL

| | |
|---|---|
| Union load (no GL) | 42.2 ms |
| Transition, median | **2.50 ms** |
| Transition, worst | **4.17 ms** |
| Frame budget @ 60 fps | 16.67 ms |

The worst transition sits at roughly a quarter of one frame. This measures exactly the work the union model claims is all a transition does: deepcopy the state dict, apply parameters by node id, tear down and rebuild edges, one evaluation pull.

### Shader compile cost — standalone GL context

| | |
|---|---|
| Single program compile, median of 10 | 0.28 ms |
| Extrapolated floor, 15 nodes | 4.1 ms |
| Extrapolated floor, 40 nodes | 11.0 ms |

Treat these as a **floor**, not an estimate: real nodes compile more than one program each, and a standalone context may optimise differently from the app's Qt GL widget. The useful conclusion is directional — compilation is cheap enough that front-loading it at session load should cost well under a second, not the "several seconds" the spec cautiously predicted.

### What these numbers do and don't establish

**Do:** the non-GL work in a transition is far inside a frame budget, and shader compilation is not expensive enough to make union loading painful.

**Don't:** they use plain `Node` objects. They do not exercise `ShaderNode.deserialize`, FBO reallocation, uniform rebinding, or the actual render pull. The remaining risk is that something in *those* paths does work proportional to the transition — and only the real app will show it.

## Manual verification — outstanding

These require running the app and watching the output. Steps 3 and 4 are the ones that matter; the rest are confirmations.

### 1. Build a real session

```bash
.venv/bin/python main.py
```

Open `saved/gs.json`. Then `Session → New Session` and:

1. `Session → Capture State` — captures the current graph as state 0.
2. Add a shader node, wire it in, `Capture State` again.
3. Repeat to **at least 8 states** and **at least 12 distinct nodes** across the union.
4. `Session → Save Session` → `saved/verification.pnlive`.

### 2. Measure real session load

Restart, then `Session → Open Session` on that file. Time from click to the dock populating.

```bash
PYTHONPATH=. .venv/bin/python -c "
from session.model import LiveSession
s = LiveSession.load('saved/verification.pnlive')
print('states:', len(s.states), 'union nodes:', len(s.compute_union()))
"
```

Record union size and wall-clock load. **If load exceeds ~30 s, stop and report** — the union model would need the background-compile fallback the spec deferred.

### 3. Measure real transition cost — the decisive test

With the session loaded and a shader graph rendering, step through every state with `Next ▶` and watch the output window.

For each transition, record whether the output visibly hitched, stuttered, or dropped frames.

**This is the plan's primary technical risk.** If any transition hitches, note which state pair and what nodes differ between them, and report before merging — it would mean the union model's central claim is wrong, which is a design problem rather than a bug.

### 4. Verify audio triggers

Edit `saved/verification.pnlive` and set state 1's trigger to:

```json
{"type": "audio", "feature": "kick_count", "count": 8}
```

Reload the session, press Play with audio running.

Expected: advances on the 8th kick, not before — and critically, **not immediately on load.** The cold-start bug that would have caused an instant advance was found and fixed in Task 6; this confirms it in the real app.

### 5. Verify the degraded path

Corrupt one node's `op_code` to `999999`. Reload.

Expected: banner lists the problem with its state index; `Play` does nothing while the banner is up; `Run anyway` dismisses the banner but the affected state keeps its ⚠ marker; playback then works with that node absent.

### 6. Verify propagation end to end

Jump to state 2, change a shader parameter in the Inspector, `Session → Overwrite State`.

Expected: a dialog reports how many later states receive the change. Apply, jump to state 5, confirm the value carried.

Then change that same parameter **only** in state 6, return to state 2, change it again, overwrite. Expected: state 6 is reported as **skipped** and keeps its own value.

Finally, delete a node in state 2 that a later state wired into, and overwrite. Expected: the later state is reported as skipped and keeps the node — the protection rule added during Task 8.

### 7. Record results

Append observations to this file under "Manual results" and commit.

## Manual results

_Not yet run._

---

## Known limitations shipped deliberately

Triaged during the final whole-branch review and judged acceptable to ship. Recorded here so they are discoverable later rather than rediscovered.

### Missing UI — the biggest gap

**There is no way to set a trigger from the application.** Every captured state is written as `{"type": "manual"}`, and making a state wait on audio requires hand-editing the `.pnlive` JSON. The engine fully supports counter and threshold triggers, and validation covers them — only the control is missing. This is a scoping miss in the implementation plan, not a defect in the code.

Also specified in the design but not built: Save As, Delete State, drag-to-reorder, rename, and key/MIDI-bound transport. The dock currently offers Play/Pause/Prev/Next and click-to-jump.

### Propagation

- `diff_scene_params` walks only the current scene's parameters, so a uniform **added to** or **removed from** a shader is not propagated — `ParamChange` has no way to express either. Later states keep whatever they had.
- `PropagationOutcome.applied` holds `(int, ParamChange)` from `propagate_params` but `(int, str)` from `propagate_structure`. Deliberate; each is consumed separately.
- `propagate_structure` snapshots `node_ids`/`edge_ids` once per state, then adds before removing. Safe only because `diff_scene_structure` guarantees the added and removed sets are disjoint — true for every path through the public API.

### Minor

- `Finding` defines `__eq__` without `__hash__`, so findings are unhashable. Nothing puts them in a set.
- `session/player.py`'s `except KeyError` around `make_entry_snapshot` is dead code — that function uses `.get()` throughout.
- The bad-trigger warning dedups on `current_index` alone, so re-entering a state that already warned stays silent for the rest of the session.
- `test_fix_and_reload_clears_the_owning_windows_session_player` proves `onFixAndReload` invokes its callback, but not that `createSessionDock` wires `_clearSessionPlayer`. Deleting that wiring line leaves the suite green.
