# Live Session — Verification Results

**Branch:** `feat/live-session`
**Date:** 2026-08-02
**Status:** automated portion complete; manual portion outstanding (needs the GUI and human eyes)

## What this document is for

The design rests on one claim that no unit test can prove: **a state transition compiles nothing, so the projected output does not hitch mid-set.** Everything else in the feature is covered by the 169 automated tests on this branch. This is the record of what was measured instead.

## Automated results

Harness: `.superpowers/sdd/2026-08-02-live-session/measure_session_cost.py`

Run with:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python \
    .superpowers/sdd/2026-08-02-live-session/measure_session_cost.py
```

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
