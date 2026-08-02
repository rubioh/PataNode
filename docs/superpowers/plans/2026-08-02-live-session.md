# Live Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a performer author an ordered list of graph states, save them as one `.pnlive` file, and replay them in sequence during a set, advanced manually or by audio.

**Architecture:** Union-scene model. Every node any state uses is instantiated once at session load, so all GLSL compiles up front; a state is then defined by edge topology and parameter values rather than by which nodes exist. Advancing rewires edges and applies parameters — no node construction, no shader compilation, no hitch. Pure logic (triggers, validation, propagation, the session document) lives in `session/` with no Qt or GL dependency; only `SessionPlayer` touches the scene.

**Tech Stack:** Python 3, PyQt5, ModernGL, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-02-live-session-design.md`

## Global Constraints

- **No changes to `nodeeditor/`.** The session layer sits on top of existing `Scene`/`Node`/`Edge` APIs. If a task appears to need a `nodeeditor/` change, stop and flag it.
- **numpy must stay below 2.3.** Uniform binding breaks on 2.3+. Do not upgrade it.
- **Run tests with `.venv/bin/python -m pytest`, not `uv run`.**
- **Qt tests need `QT_QPA_PLATFORM=offscreen`** to run headless.
- **`Node.deserialize` mutates the dict you pass it** — `data["inputs"].sort(...)` at `nodeeditor/node_node.py:628`. Always `copy.deepcopy` a state's scene dict before handing it to `deserialize`, or replaying a state silently corrupts the stored session.
- **`restore_window_size=False` on every `deserialize` call the player makes.** Without it `changeWindowSize` fires `reload_program()` (`node/shader_node_base.py:154-156`) and recompiles the shader mid-set. Plain `Node` ignores the kwarg via `**kwargs` (`nodeeditor/node_node.py:618`); `ShaderNode` honours it.
- **The only monotonic audio counters are `kick_count`, `hat_count`, `snare_count`** (`audio/audio_event.py:50-58`). The `on_tempo*` family is phase values, not counters (`audio/audio_bpm.py:40-53`), and must be rejected for counter-delta triggers.
- **No modal dialogs during playback.** Runtime failures go to a status callback. Modals are fine at load and while authoring.
- **Import `program.program_conf` before `node.node_conf` or `audio.*`** in any test that touches the node registry — there is a circular import otherwise. See `tests/depth/conftest.py`.

## File Structure

| File | Responsibility |
|---|---|
| `session/__init__.py` | Package marker |
| `session/trigger.py` | Pure trigger predicate + entry snapshots |
| `session/model.py` | `SessionState`, `LiveSession`: parse, serialize, atomic save, editing ops, union |
| `session/validation.py` | Pure static validation of a session, returns findings |
| `session/propagation.py` | Diff two scene dicts, propagate changes forward conditionally |
| `session/player.py` | `SessionPlayer`: owns the scene, load / goTo / transport / tick |
| `gui/widgets/session_dock.py` | State list, transport, banner |
| `tests/session/conftest.py` | Fixtures: qapp, scene, session builders |
| `tests/session/test_*.py` | One test module per source module |

Modified: `app.py` (one hook), `gui/patanode.py` (dock + menu).

---

### Task 1: Trigger evaluation

Pure functions, no Qt, no GL, no scene. This is the whole trigger system.

**Files:**
- Create: `session/__init__.py`, `session/trigger.py`
- Create: `tests/session/__init__.py`, `tests/session/test_trigger.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `COUNTER_FEATURES: tuple[str, ...]` — `("kick_count", "hat_count", "snare_count")`
  - `TriggerResult(NamedTuple)` with fields `should_advance: bool`, `entry: dict`
  - `make_entry_snapshot(trigger: dict, features: dict, now: float) -> dict`
  - `evaluate_trigger(trigger: dict, features: dict, entry: dict, now: float) -> TriggerResult`

`evaluate_trigger` returns a possibly-updated `entry`; the caller must store it back. That is how threshold-hold timing and counter-reset recovery stay pure.

- [ ] **Step 1: Write the failing tests**

Create `tests/session/__init__.py` (empty) and `tests/session/test_trigger.py`:

```python
from session.trigger import (
    COUNTER_FEATURES,
    evaluate_trigger,
    make_entry_snapshot,
)


def test_manual_trigger_never_advances():
    trigger = {"type": "manual"}
    entry = make_entry_snapshot(trigger, {"kick_count": 5}, 0.0)
    result = evaluate_trigger(trigger, {"kick_count": 500}, entry, 100.0)
    assert result.should_advance is False


def test_counter_advances_after_n_events():
    trigger = {"type": "audio", "feature": "kick_count", "count": 8}
    entry = make_entry_snapshot(trigger, {"kick_count": 100}, 0.0)

    result = evaluate_trigger(trigger, {"kick_count": 107}, entry, 1.0)
    assert result.should_advance is False

    result = evaluate_trigger(trigger, {"kick_count": 108}, entry, 2.0)
    assert result.should_advance is True


def test_counter_reset_re_snapshots_instead_of_advancing():
    """Audio engine restart drops kick_count to 0; delta goes negative."""
    trigger = {"type": "audio", "feature": "kick_count", "count": 8}
    entry = make_entry_snapshot(trigger, {"kick_count": 100}, 0.0)

    result = evaluate_trigger(trigger, {"kick_count": 2}, entry, 5.0)
    assert result.should_advance is False
    assert result.entry["count_at_entry"] == 2

    result = evaluate_trigger(trigger, {"kick_count": 10}, result.entry, 6.0)
    assert result.should_advance is True


def test_threshold_requires_sustained_hold():
    trigger = {"type": "audio", "feature": "low_slow", "above": 0.7, "hold": 2.0}
    entry = make_entry_snapshot(trigger, {"low_slow": 0.1}, 0.0)

    entry = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 10.0).entry
    result = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 11.5)
    assert result.should_advance is False

    result = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 12.0)
    assert result.should_advance is True


def test_threshold_resets_when_signal_drops():
    trigger = {"type": "audio", "feature": "low_slow", "above": 0.7, "hold": 2.0}
    entry = make_entry_snapshot(trigger, {"low_slow": 0.1}, 0.0)

    entry = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 10.0).entry
    entry = evaluate_trigger(trigger, {"low_slow": 0.2}, entry, 11.0).entry
    assert entry["above_since"] is None

    entry = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 11.5).entry
    result = evaluate_trigger(trigger, {"low_slow": 0.9}, entry, 12.6)
    assert result.should_advance is False


def test_missing_feature_never_advances():
    trigger = {"type": "audio", "feature": "nonexistent", "count": 1}
    entry = make_entry_snapshot(trigger, {}, 0.0)
    result = evaluate_trigger(trigger, {}, entry, 10.0)
    assert result.should_advance is False


def test_counter_features_are_the_three_real_counters():
    assert COUNTER_FEATURES == ("kick_count", "hat_count", "snare_count")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/session/test_trigger.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'session'`

- [ ] **Step 3: Implement**

Create `session/__init__.py` (empty) and `session/trigger.py`:

```python
"""Trigger evaluation for live sessions.

Pure functions: no Qt, no GL, no scene. A trigger decides when playback
advances from one state to the next.

`evaluate_trigger` returns a possibly-updated entry snapshot. Callers must
store it back — that is how hold-timing and counter-reset recovery stay
free of hidden state.
"""

from typing import NamedTuple

# The only monotonic counters the audio engine exposes
# (audio/audio_event.py:50-58). The on_tempo* family looks similar but is
# phase data, not counters (audio/audio_bpm.py:40-53).
COUNTER_FEATURES = ("kick_count", "hat_count", "snare_count")


class TriggerResult(NamedTuple):
    should_advance: bool
    entry: dict


def make_entry_snapshot(trigger: dict, features: dict, now: float) -> dict:
    """Capture whatever state this trigger needs to measure from."""
    if trigger.get("type") != "audio":
        return {}

    if "count" in trigger:
        return {"count_at_entry": features.get(trigger.get("feature"), 0)}

    if "above" in trigger:
        return {"above_since": None}

    return {}


def evaluate_trigger(
    trigger: dict, features: dict, entry: dict, now: float
) -> TriggerResult:
    """Decide whether playback should advance."""
    if trigger.get("type") != "audio":
        return TriggerResult(False, entry)

    value = features.get(trigger.get("feature"))
    if value is None:
        return TriggerResult(False, entry)

    if "count" in trigger:
        delta = value - entry.get("count_at_entry", 0)
        if delta < 0:
            # Audio engine restarted and the counter went back to zero.
            # Re-snapshot rather than advancing or hanging forever.
            return TriggerResult(False, {"count_at_entry": value})
        return TriggerResult(delta >= trigger["count"], entry)

    if "above" in trigger:
        if value > trigger["above"]:
            since = entry.get("above_since")
            if since is None:
                return TriggerResult(False, {"above_since": now})
            return TriggerResult(now - since >= trigger["hold"], entry)
        return TriggerResult(False, {"above_since": None})

    return TriggerResult(False, entry)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/session/test_trigger.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add session/__init__.py session/trigger.py tests/session/__init__.py tests/session/test_trigger.py
git commit -m "feat(session): add pure trigger evaluation"
```

---

### Task 2: Session document — model, persistence, editing

The `.pnlive` document: parse, serialize, atomic save, the editing operations, and the derived union.

**Files:**
- Create: `session/model.py`
- Create: `tests/session/test_model.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `SESSION_VERSION: int` — `1`
  - `class UnknownSessionVersion(Exception)`
  - `class InvalidSessionFile(Exception)`
  - `SessionState` — attributes `name: str`, `trigger: dict`, `scene: dict`; `to_dict()`, `SessionState.from_dict(data)`
  - `LiveSession` — attribute `name: str`, `states: list[SessionState]`
    - `LiveSession.from_dict(data) -> LiveSession`, `to_dict() -> dict`
    - `LiveSession.load(path) -> LiveSession`, `save(path) -> None`
    - `capture(scene: dict, name: str, after_index: int | None = None) -> int`
    - `overwrite(index: int, scene: dict) -> None`
    - `delete(index: int) -> None`
    - `move(from_index: int, to_index: int) -> None`
    - `rename(index: int, name: str) -> None`
    - `compute_union() -> list[dict]`

- [ ] **Step 1: Write the failing tests**

Create `tests/session/test_model.py`:

```python
import json

import pytest

from session.model import (
    SESSION_VERSION,
    InvalidSessionFile,
    LiveSession,
    SessionState,
    UnknownSessionVersion,
)


def make_scene(node_ids, edges=None):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": [
            {
                "id": nid,
                "title": "N%d" % nid,
                "pos_x": 0,
                "pos_y": 0,
                "inputs": [],
                "outputs": [],
                "content": {},
            }
            for nid in node_ids
        ],
        "edges": edges or [],
    }


def make_session():
    return LiveSession(
        name="set",
        states=[
            SessionState("intro", {"type": "manual"}, make_scene([1, 2])),
            SessionState("build", {"type": "manual"}, make_scene([1, 2, 3])),
        ],
    )


def test_round_trip_preserves_states():
    session = make_session()
    restored = LiveSession.from_dict(session.to_dict())

    assert restored.name == "set"
    assert [s.name for s in restored.states] == ["intro", "build"]
    assert restored.states[1].scene["nodes"][2]["id"] == 3


def test_to_dict_writes_current_version():
    assert make_session().to_dict()["version"] == SESSION_VERSION


def test_unknown_version_is_rejected():
    data = make_session().to_dict()
    data["version"] = 99
    with pytest.raises(UnknownSessionVersion):
        LiveSession.from_dict(data)


def test_missing_version_is_rejected():
    data = make_session().to_dict()
    del data["version"]
    with pytest.raises(UnknownSessionVersion):
        LiveSession.from_dict(data)


def test_load_rejects_malformed_json(tmp_path):
    path = tmp_path / "broken.pnlive"
    path.write_text('{"version": 1, "states": [')
    with pytest.raises(InvalidSessionFile):
        LiveSession.load(str(path))


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "set.pnlive"
    make_session().save(str(path))

    restored = LiveSession.load(str(path))
    assert [s.name for s in restored.states] == ["intro", "build"]


def test_failed_save_leaves_existing_file_intact(tmp_path, monkeypatch):
    path = tmp_path / "set.pnlive"
    original = "PRECIOUS"
    path.write_text(original)

    session = make_session()
    monkeypatch.setattr(
        session, "to_dict", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    with pytest.raises(RuntimeError):
        session.save(str(path))

    assert path.read_text() == original
    assert not (tmp_path / "set.pnlive.tmp").exists()


def test_compute_union_yields_one_node_per_id():
    union = make_session().compute_union()
    assert sorted(n["id"] for n in union) == [1, 2, 3]


def test_capture_appends_after_current():
    session = make_session()
    index = session.capture(make_scene([1, 2, 3, 4]), "drop", after_index=0)

    assert index == 1
    assert [s.name for s in session.states] == ["intro", "drop", "build"]


def test_capture_with_no_index_appends_at_end():
    session = make_session()
    index = session.capture(make_scene([9]), "outro")

    assert index == 2
    assert session.states[2].name == "outro"


def test_overwrite_replaces_scene_but_keeps_name_and_trigger():
    session = make_session()
    session.states[0].trigger = {"type": "audio", "feature": "kick_count", "count": 4}
    session.overwrite(0, make_scene([7]))

    assert session.states[0].name == "intro"
    assert session.states[0].trigger["count"] == 4
    assert session.states[0].scene["nodes"][0]["id"] == 7


def test_delete_and_move_reorder_states():
    session = make_session()
    session.capture(make_scene([5]), "outro")

    session.move(0, 2)
    assert [s.name for s in session.states] == ["build", "outro", "intro"]

    session.delete(1)
    assert [s.name for s in session.states] == ["build", "intro"]


def test_rename():
    session = make_session()
    session.rename(1, "drop")
    assert session.states[1].name == "drop"


def test_saved_file_is_valid_json_with_states(tmp_path):
    path = tmp_path / "set.pnlive"
    make_session().save(str(path))

    data = json.loads(path.read_text())
    assert data["version"] == SESSION_VERSION
    assert len(data["states"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/session/test_model.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'session.model'`

- [ ] **Step 3: Implement**

Create `session/model.py`:

```python
"""The .pnlive session document.

A session is an ordered list of states. A state is a normal scene snapshot
(exactly what Scene.serialize produces) plus a name and a trigger, so every
state stays independently loadable as a plain .pn file.

Pure data: no Qt, no GL.
"""

import json
import os

SESSION_VERSION = 1


class UnknownSessionVersion(Exception):
    """Session file has a version this build cannot read."""


class InvalidSessionFile(Exception):
    """Session file is not valid JSON."""


class SessionState:
    def __init__(self, name: str, trigger: dict, scene: dict):
        self.name = name
        self.trigger = trigger
        self.scene = scene

    def to_dict(self) -> dict:
        return {"name": self.name, "trigger": self.trigger, "scene": self.scene}

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(
            name=data.get("name", ""),
            trigger=data.get("trigger", {"type": "manual"}),
            scene=data["scene"],
        )


class LiveSession:
    def __init__(self, name: str = "", states: list = None):
        self.name = name
        self.states = states if states is not None else []

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "version": SESSION_VERSION,
            "name": self.name,
            "states": [state.to_dict() for state in self.states],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LiveSession":
        version = data.get("version")
        if version != SESSION_VERSION:
            raise UnknownSessionVersion(
                "Session format version %r is not supported (expected %d)"
                % (version, SESSION_VERSION)
            )
        return cls(
            name=data.get("name", ""),
            states=[SessionState.from_dict(s) for s in data.get("states", [])],
        )

    @classmethod
    def load(cls, path: str) -> "LiveSession":
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidSessionFile(
                "%s is not a valid session file: %s" % (os.path.basename(path), exc)
            )

        return cls.from_dict(data)

    def save(self, path: str) -> None:
        """Atomic write: a failed save never damages the existing file."""
        payload = json.dumps(self.to_dict(), indent=4)

        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    # -- editing ----------------------------------------------------------

    def capture(self, scene: dict, name: str, after_index: int = None) -> int:
        state = SessionState(name, {"type": "manual"}, scene)
        if after_index is None:
            self.states.append(state)
            return len(self.states) - 1

        index = after_index + 1
        self.states.insert(index, state)
        return index

    def overwrite(self, index: int, scene: dict) -> None:
        self.states[index].scene = scene

    def delete(self, index: int) -> None:
        del self.states[index]

    def move(self, from_index: int, to_index: int) -> None:
        state = self.states.pop(from_index)
        self.states.insert(to_index, state)

    def rename(self, index: int, name: str) -> None:
        self.states[index].name = name

    # -- derived ----------------------------------------------------------

    def compute_union(self) -> list:
        """Every node any state uses, one entry per id, first occurrence wins.

        This is the set instantiated at load so all GLSL compiles up front.
        """
        union = {}
        for state in self.states:
            for node in state.scene.get("nodes", []):
                union.setdefault(node["id"], node)
        return list(union.values())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/session/test_model.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add session/model.py tests/session/test_model.py
git commit -m "feat(session): add session document with atomic save and union"
```

---

### Task 3: Static validation

Pure validation over a session. Returns every problem at once, each tagged with its state index, so the dock can show one banner and mark the affected states.

Instantiation and GLSL-compile failures are *not* here — those are only discoverable by actually building nodes, and the player appends them in Task 4.

**Files:**
- Create: `session/validation.py`
- Create: `tests/session/test_validation.py`

**Interfaces:**
- Consumes: `session.model.LiveSession`, `session.trigger.COUNTER_FEATURES`
- Produces:
  - `Finding` — attributes `state_index: int`, `category: str` (`"node"` / `"edge"` / `"trigger"`), `message: str`
  - `validate_session(session, known_opcodes: set, known_features: set) -> list[Finding]`

`known_opcodes` and `known_features` are passed in rather than imported, so validation stays pure and testable without the node registry.

- [ ] **Step 1: Write the failing tests**

Create `tests/session/test_validation.py`:

```python
from session.model import LiveSession, SessionState
from session.validation import validate_session


def node(nid, op_code=100, inputs=(), outputs=()):
    return {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": op_code,
        "inputs": [{"id": sid, "index": i} for i, sid in enumerate(inputs)],
        "outputs": [{"id": sid, "index": i} for i, sid in enumerate(outputs)],
        "content": {},
    }


def scene(nodes, edges=()):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes),
        "edges": list(edges),
    }


OPCODES = {100, 200}
FEATURES = {"kick_count", "low_slow", "on_tempo8"}


def test_clean_session_produces_no_findings():
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                scene(
                    [node(1, outputs=[10]), node(2, inputs=[20])],
                    [{"id": 5, "start": 10, "end": 20, "edge_type": 2}],
                ),
            )
        ]
    )
    assert validate_session(session, OPCODES, FEATURES) == []


def test_unregistered_opcode_is_reported():
    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, scene([node(1, op_code=999)]))]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 1
    assert findings[0].category == "node"
    assert findings[0].state_index == 0
    assert "999" in findings[0].message


def test_edge_referencing_missing_socket_is_reported():
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                scene(
                    [node(1, outputs=[10])],
                    [{"id": 5, "start": 10, "end": 99, "edge_type": 2}],
                ),
            )
        ]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 1
    assert findings[0].category == "edge"


def test_trigger_with_unknown_feature_is_reported():
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "nope", "above": 0.5, "hold": 1.0},
                scene([node(1)]),
            )
        ]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 1
    assert findings[0].category == "trigger"


def test_counter_trigger_on_non_counter_feature_is_reported():
    """on_tempo8 is a phase value, not a counter -- unusable for count triggers."""
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "on_tempo8", "count": 8},
                scene([node(1)]),
            )
        ]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 1
    assert findings[0].category == "trigger"
    assert "counter" in findings[0].message.lower()


def test_counter_trigger_on_real_counter_is_accepted():
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "kick_count", "count": 8},
                scene([node(1)]),
            )
        ]
    )
    assert validate_session(session, OPCODES, FEATURES) == []


def test_all_findings_reported_together_with_state_indices():
    session = LiveSession(
        states=[
            SessionState("a", {"type": "manual"}, scene([node(1, op_code=999)])),
            SessionState(
                "b",
                {"type": "audio", "feature": "nope", "count": 2},
                scene([node(2, op_code=888)]),
            ),
        ]
    )
    findings = validate_session(session, OPCODES, FEATURES)

    assert len(findings) == 3
    assert {f.state_index for f in findings} == {0, 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/session/test_validation.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'session.validation'`

- [ ] **Step 3: Implement**

Create `session/validation.py`:

```python
"""Static validation of a live session.

Pure: takes the registry contents as arguments rather than importing them,
so it needs neither the node registry nor a GL context.

Every problem in the session is collected in one pass. Instantiation and
GLSL-compile failures are not detectable here -- SessionPlayer.load appends
those.
"""

from session.trigger import COUNTER_FEATURES


class Finding:
    def __init__(self, state_index: int, category: str, message: str):
        self.state_index = state_index
        self.category = category
        self.message = message

    def __repr__(self):
        return "<Finding state=%d %s: %s>" % (
            self.state_index,
            self.category,
            self.message,
        )

    def __eq__(self, other):
        return (
            isinstance(other, Finding)
            and self.state_index == other.state_index
            and self.category == other.category
            and self.message == other.message
        )


def validate_session(session, known_opcodes: set, known_features: set) -> list:
    findings = []

    for index, state in enumerate(session.states):
        findings.extend(_validate_nodes(index, state, known_opcodes))
        findings.extend(_validate_edges(index, state))
        findings.extend(_validate_trigger(index, state, known_features))

    return findings


def _validate_nodes(index, state, known_opcodes):
    findings = []
    for node in state.scene.get("nodes", []):
        if "op_code" not in node:
            findings.append(
                Finding(
                    index,
                    "node",
                    "Node '%s' has no op_code and cannot be rebuilt"
                    % node.get("title", "<untitled>"),
                )
            )
        elif node["op_code"] not in known_opcodes:
            findings.append(
                Finding(
                    index,
                    "node",
                    "Node '%s' uses unregistered op_code %s"
                    % (node.get("title", "<untitled>"), node["op_code"]),
                )
            )
    return findings


def _validate_edges(index, state):
    socket_ids = set()
    for node in state.scene.get("nodes", []):
        for socket in node.get("inputs", []) + node.get("outputs", []):
            socket_ids.add(socket["id"])

    findings = []
    for edge in state.scene.get("edges", []):
        for end in ("start", "end"):
            if edge.get(end) not in socket_ids:
                findings.append(
                    Finding(
                        index,
                        "edge",
                        "Edge %s references a %s socket that no node provides"
                        % (edge.get("id", "<unknown>"), end),
                    )
                )
    return findings


def _validate_trigger(index, state, known_features):
    trigger = state.trigger or {}
    if trigger.get("type") != "audio":
        return []

    feature = trigger.get("feature")
    if feature not in known_features:
        return [
            Finding(
                index,
                "trigger",
                "Trigger uses unknown audio feature '%s'" % feature,
            )
        ]

    if "count" in trigger and feature not in COUNTER_FEATURES:
        return [
            Finding(
                index,
                "trigger",
                "Trigger counts on '%s', which is not a counter. "
                "Only %s can be counted." % (feature, ", ".join(COUNTER_FEATURES)),
            )
        ]

    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/session/test_validation.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add session/validation.py tests/session/test_validation.py
git commit -m "feat(session): add static session validation"
```

---

### Task 4: SessionPlayer.load — union instantiation

Builds every node once so all GLSL compiles up front. Collects instantiation failures as findings and merges them with static validation.

**Files:**
- Create: `session/player.py`
- Create: `tests/session/conftest.py`, `tests/session/test_player_load.py`

**Interfaces:**
- Consumes: `session.model.LiveSession`, `session.validation.validate_session` / `Finding`
- Produces:
  - `SessionPlayer(scene, on_status=None, on_evaluate=None)`
    - `scene` — a `nodeeditor.node_scene.Scene`
    - `on_status` — `Callable[[str], None]`, non-modal runtime reporting
    - `on_evaluate` — `Callable[[], None]`, pulls one render after a transition settles. **Passed in explicitly: `Scene` has no back-reference to its subwindow** (`gui/subwindow.py:99-102` sets `ctx`, `app`, `gl_widget`, `fbo_manager` and nothing else), so the player cannot reach `doEvalOutputs` on its own. The GUI passes `editor.doEvalOutputs`; tests pass a recorder.
  - `load(session, known_opcodes: set, known_features: set) -> list[Finding]`
  - attributes: `session`, `current_index: int` (`-1` before any `goTo`), `findings: list[Finding]`

- [ ] **Step 1: Write the failing tests**

Create `tests/session/conftest.py`:

```python
"""Fixtures for session tests.

Plain nodeeditor Node/Edge need no GL context, but Scene builds a
QDMGraphicsScene, which needs a live QApplication.
"""

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def scene(qapp):
    from nodeeditor.node_scene import Scene
    from nodeeditor.node_node import Node

    built = Scene()
    # Every node in these tests is a plain Node; the union model only needs
    # a class, and plain Node ignores restore_window_size via **kwargs.
    built.setNodeClassSelector(lambda data: Node)
    return built
```

Create `tests/session/test_player_load.py`:

```python
from session.model import LiveSession, SessionState
from session.player import SessionPlayer


def node(nid, op_code=100, outputs=()):
    return {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": op_code,
        "inputs": [],
        "outputs": [{"id": sid, "index": i} for i, sid in enumerate(outputs)],
        "content": {},
    }


def make_scene(nodes, edges=()):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes),
        "edges": list(edges),
    }


OPCODES = {100}
FEATURES = {"kick_count"}


def test_load_instantiates_the_union_once(scene):
    session = LiveSession(
        states=[
            SessionState("a", {"type": "manual"}, make_scene([node(1), node(2)])),
            SessionState(
                "b", {"type": "manual"}, make_scene([node(1), node(2), node(3)])
            ),
        ]
    )
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)

    assert len(scene.nodes) == 3
    assert sorted(n.id for n in scene.nodes) == [1, 2, 3]


def test_load_wires_no_edges(scene):
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                make_scene(
                    [node(1, outputs=[10]), node(2)],
                    [{"id": 5, "start": 10, "end": 10, "edge_type": 2}],
                ),
            )
        ]
    )
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)

    assert scene.edges == []


def test_load_returns_static_findings(scene):
    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, make_scene([node(1, 999)]))]
    )
    player = SessionPlayer(scene)
    findings = player.load(session, OPCODES, FEATURES)

    assert any(f.category == "node" for f in findings)


def test_load_reports_instantiation_failure_as_finding(scene):
    def explode(data):
        raise ValueError("cannot build node")

    scene.setNodeClassSelector(explode)

    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, make_scene([node(1)]))]
    )
    player = SessionPlayer(scene)
    findings = player.load(session, OPCODES, FEATURES)

    assert any(f.category == "node" and "cannot build node" in f.message
               for f in findings)


def test_load_does_not_mutate_the_stored_session(scene):
    """Node.deserialize sorts data['inputs'] in place -- deepcopy guards it."""
    state_scene = make_scene([node(1)])
    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, state_scene)]
    )
    before = state_scene["nodes"][0].copy()

    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)

    assert state_scene["nodes"][0] == before


def test_current_index_is_minus_one_before_goto(scene):
    session = LiveSession(
        states=[SessionState("a", {"type": "manual"}, make_scene([node(1)]))]
    )
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)

    assert player.current_index == -1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/session/test_player_load.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'session.player'`

- [ ] **Step 3: Implement**

Create `session/player.py`:

```python
"""Drives a live session against a scene.

Union model: every node any state uses is instantiated once at load, so all
GLSL compiles up front. A state then only rewires edges and applies
parameter values -- no construction, no compilation, no hitch mid-set.
"""

import copy

from session.validation import Finding, validate_session


class SessionPlayer:
    def __init__(self, scene, on_status=None, on_evaluate=None):
        self.scene = scene
        self.on_status = on_status or (lambda message: None)
        # Scene has no back-reference to its subwindow, so the render pull
        # has to be handed in. GUI passes editor.doEvalOutputs.
        self.on_evaluate = on_evaluate or (lambda: None)

        self.session = None
        self.current_index = -1
        self.findings = []

    def load(self, session, known_opcodes: set, known_features: set) -> list:
        """Instantiate the union and return every problem found.

        This is the slow step: it compiles every shader the session uses.
        """
        self.session = session
        self.current_index = -1
        self.findings = validate_session(session, known_opcodes, known_features)

        union = session.compute_union()
        union_scene = {
            "id": self.scene.id,
            "scene_width": self.scene.scene_width,
            "scene_height": self.scene.scene_height,
            # deepcopy: Node.deserialize sorts data["inputs"] in place
            # (nodeeditor/node_node.py:628) and would corrupt the session.
            "nodes": copy.deepcopy(union),
            "edges": [],
        }

        self.scene.deserialize(union_scene)

        for message in self.scene.deserialization_errors:
            self.findings.append(Finding(-1, "node", message))

        return self.findings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/session/test_player_load.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add session/player.py tests/session/conftest.py tests/session/test_player_load.py
git commit -m "feat(session): instantiate union at session load"
```

---

### Task 5: SessionPlayer.goTo — transitions

The performance-critical path. Applies parameters, rewires edges, evaluates once, and is all-or-nothing.

**Files:**
- Modify: `session/player.py`
- Create: `tests/session/test_player_goto.py`

**Interfaces:**
- Consumes: `SessionPlayer` from Task 4
- Produces:
  - `SessionPlayer.goTo(index: int) -> bool` — `True` on success, `False` if the transition failed and was rolled back
  - `SessionPlayer.next() -> bool`, `SessionPlayer.prev() -> bool`

- [ ] **Step 1: Write the failing tests**

Create `tests/session/test_player_goto.py`:

```python
import pytest

from session.model import LiveSession, SessionState
from session.player import SessionPlayer


def node(nid, op_code=100, inputs=(), outputs=()):
    return {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": op_code,
        "inputs": [
            {
                "id": sid,
                "index": i,
                "multi_edges": False,
                "position": 2,
                "socket_type": 1,
            }
            for i, sid in enumerate(inputs)
        ],
        "outputs": [
            {
                "id": sid,
                "index": i,
                "multi_edges": True,
                "position": 5,
                "socket_type": 1,
            }
            for i, sid in enumerate(outputs)
        ],
        "content": {},
    }


def make_scene(nodes, edges=()):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes),
        "edges": list(edges),
    }


OPCODES = {100}
FEATURES = {"kick_count"}


@pytest.fixture
def loaded(scene):
    """Two states: state 0 has no edges, state 1 wires node 1 -> node 2."""
    n1 = node(1, outputs=[10])
    n2 = node(2, inputs=[20])
    session = LiveSession(
        states=[
            SessionState("a", {"type": "manual"}, make_scene([n1, n2])),
            SessionState(
                "b",
                {"type": "manual"},
                make_scene([n1, n2], [{"id": 5, "start": 10, "end": 20,
                                       "edge_type": 2}]),
            ),
        ]
    )
    player = SessionPlayer(scene)
    player.load(session, OPCODES, FEATURES)
    return player


def test_goto_wires_the_states_edges(loaded):
    assert loaded.goTo(1) is True

    assert len(loaded.scene.edges) == 1
    assert loaded.scene.edges[0].start_socket.id == 10
    assert loaded.scene.edges[0].end_socket.id == 20


def test_goto_back_removes_edges(loaded):
    loaded.goTo(1)
    loaded.goTo(0)

    assert loaded.scene.edges == []


def test_goto_never_destroys_union_nodes(loaded):
    loaded.goTo(0)
    assert len(loaded.scene.nodes) == 2

    loaded.goTo(1)
    assert len(loaded.scene.nodes) == 2


def test_goto_is_idempotent(loaded):
    loaded.goTo(1)
    loaded.goTo(1)

    assert len(loaded.scene.edges) == 1


def test_goto_updates_current_index(loaded):
    loaded.goTo(1)
    assert loaded.current_index == 1


def test_next_and_prev_walk_the_session(loaded):
    loaded.goTo(0)

    assert loaded.next() is True
    assert loaded.current_index == 1

    assert loaded.prev() is True
    assert loaded.current_index == 0


def test_next_at_end_does_not_advance(loaded):
    loaded.goTo(1)
    assert loaded.next() is False
    assert loaded.current_index == 1


def test_prev_at_start_does_not_move(loaded):
    loaded.goTo(0)
    assert loaded.prev() is False
    assert loaded.current_index == 0


def test_failed_transition_leaves_scene_on_current_state(loaded):
    loaded.goTo(1)

    # Corrupt the target state so building it raises
    loaded.session.states[0].scene["edges"] = [
        {"id": 7, "start": 999, "end": 998, "edge_type": 2}
    ]

    assert loaded.goTo(0) is False
    assert loaded.current_index == 1
    assert len(loaded.scene.edges) == 1


def test_goto_does_not_mutate_the_stored_session(loaded):
    before = [dict(n) for n in loaded.session.states[1].scene["nodes"]]
    loaded.goTo(1)
    assert loaded.session.states[1].scene["nodes"] == before


def test_goto_pulls_exactly_one_render(scene):
    """The transition must re-render, and must not cascade doing it."""
    calls = []
    n1 = node(1, outputs=[10])
    n2 = node(2, inputs=[20])
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                make_scene([n1, n2], [{"id": 5, "start": 10, "end": 20,
                                       "edge_type": 2}]),
            )
        ]
    )
    player = SessionPlayer(scene, on_evaluate=lambda: calls.append(1))
    player.load(session, OPCODES, FEATURES)

    assert player.goTo(0) is True
    assert len(calls) == 1


def test_failed_goto_does_not_pull_a_render(scene):
    calls = []
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                make_scene(
                    [node(1)], [{"id": 7, "start": 999, "end": 998, "edge_type": 2}]
                ),
            )
        ]
    )
    player = SessionPlayer(scene, on_evaluate=lambda: calls.append(1))
    player.load(session, OPCODES, FEATURES)

    assert player.goTo(0) is False
    assert calls == []


def test_goto_reports_failure_through_status_callback(scene):
    messages = []
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                make_scene(
                    [node(1)], [{"id": 7, "start": 999, "end": 998, "edge_type": 2}]
                ),
            )
        ]
    )
    player = SessionPlayer(scene, on_status=messages.append)
    player.load(session, OPCODES, FEATURES)

    assert player.goTo(0) is False
    assert messages
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/session/test_player_goto.py -v`
Expected: FAIL, `AttributeError: 'SessionPlayer' object has no attribute 'goTo'`

- [ ] **Step 3: Implement**

Add to `session/player.py` — the imports at the top become:

```python
import copy

from nodeeditor.node_edge import Edge
from session.validation import Finding, validate_session
```

and append these methods to `SessionPlayer`:

```python
    # -- transport --------------------------------------------------------

    def goTo(self, index: int) -> bool:
        """Switch to state `index`. All-or-nothing.

        Resolves everything against a staging structure first, so a failure
        leaves the scene untouched on the state it was already showing.
        """
        if self.session is None or not (0 <= index < len(self.session.states)):
            return False

        state = self.session.states[index]

        # deepcopy: Node.deserialize sorts data["inputs"] in place
        # (nodeeditor/node_node.py:628).
        scene_data = copy.deepcopy(state.scene)

        try:
            staged_edges = self._stage_edges(scene_data)
        except KeyError as exc:
            self.on_status(
                "Could not switch to state '%s': missing socket %s" % (state.name, exc)
            )
            return False

        self._apply_parameters(scene_data)
        self._rewire(staged_edges)

        self.current_index = index
        self._evaluate_once()
        return True

    def next(self) -> bool:
        return self.goTo(self.current_index + 1)

    def prev(self) -> bool:
        if self.current_index <= 0:
            return False
        return self.goTo(self.current_index - 1)

    # -- internals --------------------------------------------------------

    def _socket_index(self) -> dict:
        index = {}
        for node in self.scene.nodes:
            for socket in node.inputs + node.outputs:
                index[socket.id] = socket
        return index

    def _stage_edges(self, scene_data: dict) -> list:
        """Resolve every edge to real sockets before touching the scene.

        Raises KeyError if any endpoint is missing -- which is why a failed
        transition cannot half-apply.
        """
        sockets = self._socket_index()
        staged = []
        for edge_data in scene_data.get("edges", []):
            staged.append(
                (sockets[edge_data["start"]], sockets[edge_data["end"]],
                 edge_data.get("edge_type", 2))
            )
        return staged

    def _apply_parameters(self, scene_data: dict) -> None:
        by_id = {node.id: node for node in self.scene.nodes}
        for node_data in scene_data.get("nodes", []):
            node = by_id.get(node_data["id"])
            if node is None:
                continue
            # restore_window_size=False: otherwise changeWindowSize fires
            # reload_program() and recompiles the shader mid-set.
            node.deserialize(node_data, {}, True, restore_window_size=False)

    def _rewire(self, staged_edges: list) -> None:
        for edge in list(self.scene.edges):
            edge.remove()

        for start_socket, end_socket, edge_type in staged_edges:
            Edge(self.scene, start_socket, end_socket, edge_type)

    def _evaluate_once(self) -> None:
        """One render pull after the graph has settled.

        Edge assignment fires onInputChanged per socket
        (nodeeditor/node_edge.py:300), so evaluating during the rewire would
        cascade. Doing it once at the end avoids that.
        """
        self.on_evaluate()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/session/test_player_goto.py -v`
Expected: 13 passed

- [ ] **Step 5: Run the whole suite for regressions**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add session/player.py tests/session/test_player_goto.py
git commit -m "feat(session): add all-or-nothing state transitions"
```

---

### Task 6: Playback and trigger evaluation

Wires triggers into the running app.

**Files:**
- Modify: `session/player.py`
- Modify: `app.py:118-119`
- Create: `tests/session/test_player_playback.py`

**Interfaces:**
- Consumes: `session.trigger.evaluate_trigger` / `make_entry_snapshot`, `SessionPlayer` from Task 5
- Produces:
  - `SessionPlayer.play() -> None`, `SessionPlayer.pause() -> None`
  - `SessionPlayer.is_playing: bool`
  - `SessionPlayer.tick(features: dict, now: float) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/session/test_player_playback.py`:

```python
import pytest

from session.model import LiveSession, SessionState
from session.player import SessionPlayer


def node(nid):
    return {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": 100,
        "inputs": [],
        "outputs": [],
        "content": {},
    }


def make_scene(nodes):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes),
        "edges": [],
    }


@pytest.fixture
def player(scene):
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "audio", "feature": "kick_count", "count": 4},
                make_scene([node(1)]),
            ),
            SessionState("b", {"type": "manual"}, make_scene([node(1), node(2)])),
            SessionState("c", {"type": "manual"}, make_scene([node(1)])),
        ]
    )
    built = SessionPlayer(scene)
    built.load(session, {100}, {"kick_count"})
    built.goTo(0)
    return built


def test_tick_does_nothing_while_paused(player):
    player.pause()
    player.tick({"kick_count": 999}, 10.0)
    assert player.current_index == 0


def test_tick_advances_when_counter_trigger_fires(player):
    player.play()

    player.tick({"kick_count": 2}, 1.0)
    assert player.current_index == 0

    player.tick({"kick_count": 4}, 2.0)
    assert player.current_index == 1


def test_manual_trigger_never_auto_advances(player):
    player.goTo(1)
    player.play()

    player.tick({"kick_count": 9999}, 50.0)
    assert player.current_index == 1


def test_manual_next_works_while_playing_and_waiting(player):
    player.play()
    assert player.next() is True
    assert player.current_index == 1


def test_entry_snapshot_resets_on_each_state(player):
    player.play()
    player.tick({"kick_count": 4}, 1.0)
    assert player.current_index == 1

    player.goTo(0)
    player.tick({"kick_count": 5}, 2.0)
    assert player.current_index == 0


def test_playback_stops_at_the_last_state(player):
    player.goTo(2)
    player.play()
    player.tick({"kick_count": 9999}, 99.0)
    assert player.current_index == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/session/test_player_playback.py -v`
Expected: FAIL, `AttributeError: 'SessionPlayer' object has no attribute 'pause'`

- [ ] **Step 3: Implement**

In `session/player.py`, extend the imports:

```python
from session.trigger import evaluate_trigger, make_entry_snapshot
```

In `SessionPlayer.__init__`, add:

```python
        self.is_playing = False
        self._entry = {}
```

At the end of `goTo`, replace `self._evaluate_once()` and `return True` with:

```python
        self.current_index = index
        self._entry = make_entry_snapshot(state.trigger, self._last_features, self._now)
        self._evaluate_once()
        return True
```

and add to `__init__`:

```python
        self._last_features = {}
        self._now = 0.0
```

Append the transport methods:

```python
    def play(self) -> None:
        self.is_playing = True

    def pause(self) -> None:
        self.is_playing = False

    def tick(self, features: dict, now: float) -> None:
        """Called from the audio timer. Advances if the trigger fires."""
        self._last_features = features
        self._now = now

        if not self.is_playing or self.session is None:
            return
        if not (0 <= self.current_index < len(self.session.states)):
            return

        trigger = self.session.states[self.current_index].trigger
        result = evaluate_trigger(trigger, features, self._entry, now)
        self._entry = result.entry

        if result.should_advance:
            self.next()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/session/test_player_playback.py -v`
Expected: 6 passed

- [ ] **Step 5: Hook into the audio timer**

In `app.py`, `on_audio_job_finished` currently reads:

```python
    def on_audio_job_finished(self):
        self.set_audio_features()
```

Change it to:

```python
    def on_audio_job_finished(self):
        self.set_audio_features()
        if self.session_player is not None:
            self.session_player.tick(self.last_audio_features, time.monotonic())
```

Add `import time` to the top of `app.py`.

**`PataShadeApp` *is* the main window** — it subclasses `PataNode` (`app.py:35`), and `main.py:49` instantiates it directly. There is no `self.app` attribute on it. So declare the player on the base class, in `PataNode.__init__` (`gui/patanode.py:49-56`), alongside `self.active_graph = None`:

```python
        self.session_player = None
        self.session_filename = None
```

Every handler in Task 9 then reaches it as `self.session_player`, and `on_audio_job_finished` above sees it through inheritance.

- [ ] **Step 6: Verify the app still starts**

Run: `.venv/bin/python main.py`
Expected: app opens normally, no traceback. Close it.

- [ ] **Step 7: Commit**

```bash
git add session/player.py app.py tests/session/test_player_playback.py
git commit -m "feat(session): add playback with audio-driven triggers"
```

---

### Task 7: Parameter propagation

Diff a baseline scene against an edited one, then push those changes forward through later states — skipping any state that changed the value independently.

**Files:**
- Create: `session/propagation.py`
- Create: `tests/session/test_propagation.py`

**Interfaces:**
- Consumes: `session.model.LiveSession`
- Produces:
  - `ParamChange` — `node_id: int`, `kind: str` (`"cpu"` / `"gpu"`), `program: str`, `uniform: str`, `old_value`, `new_value`
  - `PropagationOutcome` — `applied: list[tuple[int, ParamChange]]`, `skipped: list[tuple[int, ParamChange, object]]`
  - `diff_scene_params(baseline: dict, current: dict) -> list[ParamChange]`
  - `propagate_params(session, from_index: int, changes: list, apply: bool = True) -> PropagationOutcome`

`apply=False` gives the preview; preview and commit share one code path so they cannot disagree.

- [ ] **Step 1: Write the failing tests**

Create `tests/session/test_propagation.py`:

```python
from session.model import LiveSession, SessionState
from session.propagation import diff_scene_params, propagate_params


def node(nid, cpu=None, gpu=None):
    data = {
        "id": nid,
        "title": "N%d" % nid,
        "pos_x": 0,
        "pos_y": 0,
        "op_code": 100,
        "inputs": [],
        "outputs": [],
        "content": {},
    }
    if cpu is not None:
        data["cpu_adaptable_parameters"] = cpu
    if gpu is not None:
        data["gpu_adaptable_parameters"] = gpu
    return data


def params(**uniforms):
    return {
        "program": {
            name: {"eval_function": {"value": value}}
            for name, value in uniforms.items()
        }
    }


def make_scene(nodes):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes),
        "edges": [],
    }


def test_diff_finds_changed_cpu_parameter():
    baseline = make_scene([node(1, cpu=params(radius="0.35"))])
    current = make_scene([node(1, cpu=params(radius="0.8"))])

    changes = diff_scene_params(baseline, current)

    assert len(changes) == 1
    assert changes[0].node_id == 1
    assert changes[0].kind == "cpu"
    assert changes[0].uniform == "radius"
    assert changes[0].old_value == "0.35"
    assert changes[0].new_value == "0.8"


def test_diff_finds_changed_gpu_parameter():
    baseline = make_scene([node(1, gpu=params(speed="x"))])
    current = make_scene([node(1, gpu=params(speed="x/3"))])

    changes = diff_scene_params(baseline, current)

    assert len(changes) == 1
    assert changes[0].kind == "gpu"
    assert changes[0].new_value == "x/3"


def test_diff_ignores_unchanged_parameters():
    baseline = make_scene([node(1, cpu=params(radius="0.35"))])
    current = make_scene([node(1, cpu=params(radius="0.35"))])

    assert diff_scene_params(baseline, current) == []


def test_propagation_applies_where_value_still_matches():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1, cpu=params(radius="0.8"))])),
            SessionState("b", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
            SessionState("c", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
        ]
    )
    changes = [
        c
        for c in diff_scene_params(
            make_scene([node(1, cpu=params(radius="0.35"))]),
            make_scene([node(1, cpu=params(radius="0.8"))]),
        )
    ]

    outcome = propagate_params(session, 0, changes)

    assert len(outcome.applied) == 2
    assert outcome.skipped == []
    for state in session.states[1:]:
        value = state.scene["nodes"][0]["cpu_adaptable_parameters"]["program"][
            "radius"
        ]["eval_function"]["value"]
        assert value == "0.8"


def test_propagation_skips_states_that_diverged():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1, cpu=params(radius="0.8"))])),
            SessionState("b", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
            SessionState("c", {}, make_scene([node(1, cpu=params(radius="0.9"))])),
        ]
    )
    changes = diff_scene_params(
        make_scene([node(1, cpu=params(radius="0.35"))]),
        make_scene([node(1, cpu=params(radius="0.8"))]),
    )

    outcome = propagate_params(session, 0, changes)

    assert len(outcome.applied) == 1
    assert len(outcome.skipped) == 1

    state_index, change, actual = outcome.skipped[0]
    assert state_index == 2
    assert change.uniform == "radius"
    assert actual == "0.9"

    # The diverged state keeps its own value
    assert (
        session.states[2].scene["nodes"][0]["cpu_adaptable_parameters"]["program"][
            "radius"
        ]["eval_function"]["value"]
        == "0.9"
    )


def test_preview_does_not_mutate_the_session():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1, cpu=params(radius="0.8"))])),
            SessionState("b", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
        ]
    )
    changes = diff_scene_params(
        make_scene([node(1, cpu=params(radius="0.35"))]),
        make_scene([node(1, cpu=params(radius="0.8"))]),
    )

    outcome = propagate_params(session, 0, changes, apply=False)

    assert len(outcome.applied) == 1
    assert (
        session.states[1].scene["nodes"][0]["cpu_adaptable_parameters"]["program"][
            "radius"
        ]["eval_function"]["value"]
        == "0.35"
    )


def test_propagation_never_touches_earlier_states():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
            SessionState("b", {}, make_scene([node(1, cpu=params(radius="0.8"))])),
            SessionState("c", {}, make_scene([node(1, cpu=params(radius="0.35"))])),
        ]
    )
    changes = diff_scene_params(
        make_scene([node(1, cpu=params(radius="0.35"))]),
        make_scene([node(1, cpu=params(radius="0.8"))]),
    )

    propagate_params(session, 1, changes)

    assert (
        session.states[0].scene["nodes"][0]["cpu_adaptable_parameters"]["program"][
            "radius"
        ]["eval_function"]["value"]
        == "0.35"
    )


def test_propagation_ignores_states_missing_the_node():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1, cpu=params(radius="0.8"))])),
            SessionState("b", {}, make_scene([node(2)])),
        ]
    )
    changes = diff_scene_params(
        make_scene([node(1, cpu=params(radius="0.35"))]),
        make_scene([node(1, cpu=params(radius="0.8"))]),
    )

    outcome = propagate_params(session, 0, changes)

    assert outcome.applied == []
    assert outcome.skipped == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/session/test_propagation.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'session.propagation'`

- [ ] **Step 3: Implement**

Create `session/propagation.py`:

```python
"""Propagate an edit forward through later states.

Editing state 3 should be able to fix states 4..N too, but must never
clobber a value a later state deliberately changed. Hence: apply where the
old value still stands, skip and report where it does not.

Pure dict manipulation -- no Qt, no GL, no scene.
"""

PARAM_KINDS = {"cpu": "cpu_adaptable_parameters", "gpu": "gpu_adaptable_parameters"}


class ParamChange:
    def __init__(self, node_id, kind, program, uniform, old_value, new_value):
        self.node_id = node_id
        self.kind = kind
        self.program = program
        self.uniform = uniform
        self.old_value = old_value
        self.new_value = new_value

    def __repr__(self):
        return "<ParamChange node=%s %s.%s.%s %r -> %r>" % (
            self.node_id,
            self.kind,
            self.program,
            self.uniform,
            self.old_value,
            self.new_value,
        )

    def __eq__(self, other):
        return isinstance(other, ParamChange) and vars(self) == vars(other)


class PropagationOutcome:
    def __init__(self, applied=None, skipped=None):
        self.applied = applied if applied is not None else []
        self.skipped = skipped if skipped is not None else []


def _nodes_by_id(scene: dict) -> dict:
    return {node["id"]: node for node in scene.get("nodes", [])}


def _values(node: dict, kind: str):
    """Yield (program, uniform, value) for one parameter kind."""
    container = node.get(PARAM_KINDS[kind], {}) or {}
    for program, uniforms in container.items():
        for uniform, spec in uniforms.items():
            yield program, uniform, spec.get("eval_function", {}).get("value")


def _find_value(node: dict, kind: str, program: str, uniform: str):
    container = node.get(PARAM_KINDS[kind], {}) or {}
    spec = container.get(program, {}).get(uniform)
    if spec is None:
        return None, False
    return spec.get("eval_function", {}).get("value"), True


def _set_value(node: dict, kind: str, program: str, uniform: str, value) -> None:
    node[PARAM_KINDS[kind]][program][uniform]["eval_function"]["value"] = value


def diff_scene_params(baseline: dict, current: dict) -> list:
    """Every parameter whose value differs between two scene snapshots."""
    baseline_nodes = _nodes_by_id(baseline)
    changes = []

    for node_id, current_node in _nodes_by_id(current).items():
        baseline_node = baseline_nodes.get(node_id)
        if baseline_node is None:
            continue

        for kind in PARAM_KINDS:
            for program, uniform, new_value in _values(current_node, kind):
                old_value, found = _find_value(baseline_node, kind, program, uniform)
                if found and old_value != new_value:
                    changes.append(
                        ParamChange(
                            node_id, kind, program, uniform, old_value, new_value
                        )
                    )

    return changes


def propagate_params(
    session, from_index: int, changes: list, apply: bool = True
) -> PropagationOutcome:
    """Push `changes` onto states after `from_index`.

    Applies where the state still holds the old value; skips where it
    diverged. `apply=False` previews without mutating anything, so the
    preview and the commit can never disagree.
    """
    outcome = PropagationOutcome()

    for state_index in range(from_index + 1, len(session.states)):
        nodes = _nodes_by_id(session.states[state_index].scene)

        for change in changes:
            node = nodes.get(change.node_id)
            if node is None:
                continue

            actual, found = _find_value(
                node, change.kind, change.program, change.uniform
            )
            if not found:
                continue

            if actual == change.old_value:
                if apply:
                    _set_value(
                        node,
                        change.kind,
                        change.program,
                        change.uniform,
                        change.new_value,
                    )
                outcome.applied.append((state_index, change))
            else:
                outcome.skipped.append((state_index, change, actual))

    return outcome
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/session/test_propagation.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add session/propagation.py tests/session/test_propagation.py
git commit -m "feat(session): propagate parameter edits forward, skipping divergence"
```

---

### Task 8: Structural propagation

Nodes and edges added or removed in an edited state, pushed forward the same conditional way.

**Files:**
- Modify: `session/propagation.py`
- Modify: `tests/session/test_propagation.py`

**Interfaces:**
- Consumes: Task 7's module
- Produces:
  - `StructuralDiff` — `added_nodes: list[dict]`, `removed_node_ids: set[int]`, `added_edges: list[dict]`, `removed_edge_ids: set[int]`
  - `diff_scene_structure(baseline: dict, current: dict) -> StructuralDiff`
  - `propagate_structure(session, from_index: int, diff: StructuralDiff, apply: bool = True) -> PropagationOutcome`

`PropagationOutcome.applied` entries here are `(state_index, description: str)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/session/test_propagation.py`:

```python
from session.propagation import diff_scene_structure, propagate_structure


def edge(eid, start, end):
    return {"id": eid, "start": start, "end": end, "edge_type": 2}


def test_structural_diff_detects_added_and_removed_nodes():
    baseline = make_scene([node(1), node(2)])
    current = make_scene([node(1), node(3)])

    diff = diff_scene_structure(baseline, current)

    assert [n["id"] for n in diff.added_nodes] == [3]
    assert diff.removed_node_ids == {2}


def test_structural_diff_detects_added_and_removed_edges():
    baseline = {**make_scene([node(1)]), "edges": [edge(10, 1, 2)]}
    current = {**make_scene([node(1)]), "edges": [edge(11, 2, 3)]}

    diff = diff_scene_structure(baseline, current)

    assert [e["id"] for e in diff.added_edges] == [11]
    assert diff.removed_edge_ids == {10}


def test_propagate_structure_adds_node_to_later_states():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1), node(3)])),
            SessionState("b", {}, make_scene([node(1)])),
        ]
    )
    diff = diff_scene_structure(make_scene([node(1)]), make_scene([node(1), node(3)]))

    outcome = propagate_structure(session, 0, diff)

    assert [n["id"] for n in session.states[1].scene["nodes"]] == [1, 3]
    assert len(outcome.applied) == 1


def test_propagate_structure_removes_node_from_later_states():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1)])),
            SessionState("b", {}, make_scene([node(1), node(2)])),
        ]
    )
    diff = diff_scene_structure(make_scene([node(1), node(2)]), make_scene([node(1)]))

    propagate_structure(session, 0, diff)

    assert [n["id"] for n in session.states[1].scene["nodes"]] == [1]


def test_propagate_structure_does_not_duplicate_existing_nodes():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1), node(3)])),
            SessionState("b", {}, make_scene([node(1), node(3)])),
        ]
    )
    diff = diff_scene_structure(make_scene([node(1)]), make_scene([node(1), node(3)]))

    propagate_structure(session, 0, diff)

    assert [n["id"] for n in session.states[1].scene["nodes"]] == [1, 3]


def test_propagate_structure_preview_does_not_mutate():
    session = LiveSession(
        states=[
            SessionState("a", {}, make_scene([node(1), node(3)])),
            SessionState("b", {}, make_scene([node(1)])),
        ]
    )
    diff = diff_scene_structure(make_scene([node(1)]), make_scene([node(1), node(3)]))

    propagate_structure(session, 0, diff, apply=False)

    assert [n["id"] for n in session.states[1].scene["nodes"]] == [1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/session/test_propagation.py -v`
Expected: FAIL, `ImportError: cannot import name 'diff_scene_structure'`

- [ ] **Step 3: Implement**

Append to `session/propagation.py`:

```python
import copy


class StructuralDiff:
    def __init__(self, added_nodes, removed_node_ids, added_edges, removed_edge_ids):
        self.added_nodes = added_nodes
        self.removed_node_ids = removed_node_ids
        self.added_edges = added_edges
        self.removed_edge_ids = removed_edge_ids


def diff_scene_structure(baseline: dict, current: dict) -> StructuralDiff:
    baseline_nodes = _nodes_by_id(baseline)
    current_nodes = _nodes_by_id(current)

    baseline_edges = {e["id"]: e for e in baseline.get("edges", [])}
    current_edges = {e["id"]: e for e in current.get("edges", [])}

    return StructuralDiff(
        added_nodes=[
            node for nid, node in current_nodes.items() if nid not in baseline_nodes
        ],
        removed_node_ids=set(baseline_nodes) - set(current_nodes),
        added_edges=[
            edge for eid, edge in current_edges.items() if eid not in baseline_edges
        ],
        removed_edge_ids=set(baseline_edges) - set(current_edges),
    )


def propagate_structure(
    session, from_index: int, diff: StructuralDiff, apply: bool = True
) -> PropagationOutcome:
    """Push node/edge additions and removals onto states after `from_index`."""
    outcome = PropagationOutcome()

    for state_index in range(from_index + 1, len(session.states)):
        scene = session.states[state_index].scene
        node_ids = {n["id"] for n in scene.get("nodes", [])}
        edge_ids = {e["id"] for e in scene.get("edges", [])}

        for node in diff.added_nodes:
            if node["id"] in node_ids:
                continue
            if apply:
                scene.setdefault("nodes", []).append(copy.deepcopy(node))
            outcome.applied.append((state_index, "added node %s" % node["id"]))

        for node_id in diff.removed_node_ids:
            if node_id not in node_ids:
                continue
            if apply:
                scene["nodes"] = [n for n in scene["nodes"] if n["id"] != node_id]
            outcome.applied.append((state_index, "removed node %s" % node_id))

        for edge in diff.added_edges:
            if edge["id"] in edge_ids:
                continue
            if apply:
                scene.setdefault("edges", []).append(copy.deepcopy(edge))
            outcome.applied.append((state_index, "added edge %s" % edge["id"]))

        for edge_id in diff.removed_edge_ids:
            if edge_id not in edge_ids:
                continue
            if apply:
                scene["edges"] = [e for e in scene["edges"] if e["id"] != edge_id]
            outcome.applied.append((state_index, "removed edge %s" % edge_id))

    return outcome
```

Move `import copy` to the top of the file alongside the other imports rather than leaving it mid-module.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/session/test_propagation.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add session/propagation.py tests/session/test_propagation.py
git commit -m "feat(session): propagate node and edge changes forward"
```

---

### Task 9: Session dock, menu, and transport

The UI. Follows the existing dock pattern at `gui/patanode.py:668-683`.

**Files:**
- Create: `gui/widgets/session_dock.py`
- Modify: `gui/patanode.py` — dock creation, `&Session` menu, handlers. (`self.session_player` / `self.session_filename` were declared in `PataNode.__init__` back in Task 6.)

**Interfaces:**
- Consumes: `SessionPlayer`, `LiveSession`, `validate_session`, `propagate_params`, `propagate_structure`
- Produces: `QDMSessionDock(QWidget)` with `setPlayer(player)`, `refresh()`, `showFindings(findings)`

- [ ] **Step 1: Build the dock widget**

Create `gui/widgets/session_dock.py`:

```python
"""Live session dock: state list, transport, and the validation banner."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

WARNING_ROLE = Qt.UserRole + 1


class QDMSessionDock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = None
        self.warned_states = set()

        layout = QVBoxLayout()

        self.banner = QLabel("")
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet(
            "background:#552222; color:#ffdddd; padding:6px; border-radius:3px;"
        )
        self.banner.hide()
        layout.addWidget(self.banner)

        self.banner_buttons = QWidget()
        banner_row = QHBoxLayout()
        self.btn_reload = QPushButton("Fix and reload")
        self.btn_run_anyway = QPushButton("Run anyway")
        banner_row.addWidget(self.btn_reload)
        banner_row.addWidget(self.btn_run_anyway)
        self.banner_buttons.setLayout(banner_row)
        self.banner_buttons.hide()
        layout.addWidget(self.banner_buttons)

        self.state_list = QListWidget()
        self.state_list.itemDoubleClicked.connect(self.onStateActivated)
        layout.addWidget(self.state_list)

        transport = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Prev")
        self.btn_play = QPushButton("▶ Play")
        self.btn_next = QPushButton("Next ▶")
        self.btn_capture = QPushButton("Capture")
        for button in (self.btn_prev, self.btn_play, self.btn_next, self.btn_capture):
            transport.addWidget(button)
        layout.addLayout(transport)

        self.setLayout(layout)

        self.btn_prev.clicked.connect(self.onPrev)
        self.btn_next.clicked.connect(self.onNext)
        self.btn_play.clicked.connect(self.onTogglePlay)
        self.btn_run_anyway.clicked.connect(self.onRunAnyway)

    def setPlayer(self, player):
        self.player = player
        self.refresh()

    def showFindings(self, findings):
        """Blocking banner. Playback cannot start until it is dismissed."""
        self.warned_states = {f.state_index for f in findings if f.state_index >= 0}

        if not findings:
            self.banner.hide()
            self.banner_buttons.hide()
            self.refresh()
            return

        lines = ["%d problem(s) found in this session:" % len(findings)]
        for finding in findings[:10]:
            where = (
                "state %d" % finding.state_index
                if finding.state_index >= 0
                else "session load"
            )
            lines.append("  • [%s] %s" % (where, finding.message))
        if len(findings) > 10:
            lines.append("  … and %d more" % (len(findings) - 10))

        self.banner.setText("\n".join(lines))
        self.banner.show()
        self.banner_buttons.show()
        self.refresh()

    def onRunAnyway(self):
        """Dismiss the banner but keep the per-state markers for the session."""
        self.banner.hide()
        self.banner_buttons.hide()

    def refresh(self):
        self.state_list.clear()
        if self.player is None or self.player.session is None:
            return

        for index, state in enumerate(self.player.session.states):
            label = "%2d  %s   [%s]" % (
                index,
                state.name or "(unnamed)",
                self._trigger_summary(state.trigger),
            )
            if index == self.player.current_index:
                label = "▶ " + label
            else:
                label = "   " + label
            if index in self.warned_states:
                label += "   ⚠"

            item = QListWidgetItem(label)
            self.state_list.addItem(item)

        self.btn_play.setText("❚❚ Pause" if self.player.is_playing else "▶ Play")

    @staticmethod
    def _trigger_summary(trigger):
        if not trigger or trigger.get("type") != "audio":
            return "manual"
        if "count" in trigger:
            return "%s ×%s" % (trigger.get("feature"), trigger.get("count"))
        return "%s > %s for %ss" % (
            trigger.get("feature"),
            trigger.get("above"),
            trigger.get("hold"),
        )

    def _bannerBlocking(self):
        return self.banner.isVisible()

    def onStateActivated(self, item):
        if self.player is None:
            return
        self.player.pause()
        self.player.goTo(self.state_list.row(item))
        self.refresh()

    def onPrev(self):
        if self.player is not None:
            self.player.prev()
            self.refresh()

    def onNext(self):
        if self.player is not None:
            self.player.next()
            self.refresh()

    def onTogglePlay(self):
        if self.player is None:
            return
        if self.player.is_playing:
            self.player.pause()
        elif not self._bannerBlocking():
            self.player.play()
        self.refresh()
```

- [ ] **Step 2: Wire the dock into the main window**

In `gui/patanode.py`, add the import:

```python
from gui.widgets.session_dock import QDMSessionDock
```

Add a `createSessionDock` method alongside `createNodesDock` (near line 668):

```python
    def createSessionDock(self):
        self.session_widget = QDMSessionDock()
        self.sessionDock = QDockWidget("Live Session")
        self.sessionDock.setWidget(self.session_widget)
        self.sessionDock.setFloating(False)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.sessionDock)
```

Call it wherever `createNodesDock()` is called in `initUI`.

- [ ] **Step 3: Add the Session menu**

In `gui/patanode.py`, inside `createMenus` (near line 569), after the Window menu:

```python
        self.sessionMenu = self.menuBar().addMenu("&Session")
        self.sessionMenu.addAction("&New Session", self.onSessionNew)
        self.sessionMenu.addAction("&Open Session…", self.onSessionOpen)
        self.sessionMenu.addAction("&Save Session", self.onSessionSave)
        self.sessionMenu.addSeparator()
        self.sessionMenu.addAction("&Capture State", self.onSessionCapture)
        self.sessionMenu.addAction("&Overwrite State", self.onSessionOverwrite)
```

Add the handlers to `PataNode`:

```python
    def onSessionNew(self):
        from session.model import LiveSession
        from session.player import SessionPlayer

        editor = self.getCurrentNodeEditorWidget()
        if editor is None:
            return

        player = SessionPlayer(
            editor.scene,
            on_status=self._sessionStatus,
            on_evaluate=editor.doEvalOutputs,
        )
        player.load(LiveSession(), self._knownOpcodes(), self._knownFeatures())
        self.session_player = player
        self.session_widget.setPlayer(player)
        self.session_filename = None

    def onSessionOpen(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        from session.model import (
            InvalidSessionFile,
            LiveSession,
            UnknownSessionVersion,
        )
        from session.player import SessionPlayer

        editor = self.getCurrentNodeEditorWidget()
        if editor is None:
            return

        fname, _ = QFileDialog.getOpenFileName(
            self, "Open live session", "saved", "Live Session (*.pnlive)"
        )
        if not fname:
            return

        try:
            session = LiveSession.load(fname)
        except (InvalidSessionFile, UnknownSessionVersion) as exc:
            QMessageBox.warning(self, "Cannot open session", str(exc))
            return

        player = SessionPlayer(
            editor.scene,
            on_status=self._sessionStatus,
            on_evaluate=editor.doEvalOutputs,
        )
        findings = player.load(session, self._knownOpcodes(), self._knownFeatures())

        self.session_player = player
        self.session_filename = fname
        self.session_widget.setPlayer(player)
        self.session_widget.showFindings(findings)
        player.goTo(0)
        self.session_widget.refresh()

    def onSessionSave(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        player = self.session_player
        if player is None or player.session is None:
            return

        fname = self.session_filename
        if not fname:
            fname, _ = QFileDialog.getSaveFileName(
                self, "Save live session", "saved", "Live Session (*.pnlive)"
            )
            if not fname:
                return

        try:
            player.session.save(fname)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Cannot save session",
                "The session could not be saved:\n\n%s\n\n"
                "Your previously saved file has not been modified." % exc,
            )
            return

        self.session_filename = fname
        self.statusBar().showMessage("Session saved to %s" % fname, 5000)

    def onSessionCapture(self):
        editor = self.getCurrentNodeEditorWidget()
        player = self.session_player
        if editor is None or player is None or player.session is None:
            return

        index = player.session.capture(
            editor.scene.serialize(),
            "state %d" % (len(player.session.states) + 1),
            after_index=player.current_index if player.current_index >= 0 else None,
        )
        player.current_index = index
        self.session_widget.refresh()

    def onSessionOverwrite(self):
        from PyQt5.QtWidgets import QMessageBox
        from session.propagation import (
            diff_scene_params,
            diff_scene_structure,
            propagate_params,
            propagate_structure,
        )

        editor = self.getCurrentNodeEditorWidget()
        player = self.session_player
        if editor is None or player is None or player.current_index < 0:
            return

        index = player.current_index
        baseline = player.session.states[index].scene
        current = editor.scene.serialize()

        param_changes = diff_scene_params(baseline, current)
        structure = diff_scene_structure(baseline, current)

        preview_params = propagate_params(
            player.session, index, param_changes, apply=False
        )
        preview_structure = propagate_structure(
            player.session, index, structure, apply=False
        )

        player.session.overwrite(index, current)

        total = len(preview_params.applied) + len(preview_structure.applied)
        if total == 0 and not preview_params.skipped:
            self.session_widget.refresh()
            return

        lines = [
            "Applying %d change(s) to states %d–%d."
            % (total, index + 1, len(player.session.states) - 1),
            "  • %d will be applied" % total,
        ]
        for state_index, change, actual in preview_params.skipped:
            lines.append(
                "  • skipped — %s in state %d was changed independently "
                "(%r, expected %r)"
                % (change.uniform, state_index, actual, change.old_value)
            )

        answer = QMessageBox.question(
            self,
            "Propagate to following states?",
            "\n".join(lines),
            QMessageBox.Apply | QMessageBox.Cancel,
        )
        if answer == QMessageBox.Apply:
            propagate_params(player.session, index, param_changes)
            propagate_structure(player.session, index, structure)

        self.session_widget.refresh()

    def _sessionStatus(self, message):
        self.statusBar().showMessage(message, 8000)

    @staticmethod
    def _knownOpcodes():
        from node.node_conf import AUDIO_NODES, SHADER_NODES

        return set(SHADER_NODES) | set(AUDIO_NODES)

    @staticmethod
    def _knownFeatures():
        from audio.audio_conf import list_audio_features

        return set(list_audio_features)
```

- [ ] **Step 4: Verify the app runs with the dock**

Run: `.venv/bin/python main.py`
Expected: app opens, `Live Session` dock visible at the bottom, `&Session` menu present. `Session → New Session` does not raise. Close the app.

- [ ] **Step 5: Run the full suite**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add gui/widgets/session_dock.py gui/patanode.py app.py
git commit -m "feat(session): add session dock, menu, and transport"
```

---

### Task 10: End-to-end verification and transition cost measurement

The spec's two untestable risks. This task is manual and produces a written result, not code.

**Files:**
- Create: `docs/superpowers/plans/2026-08-02-live-session-verification.md`

- [ ] **Step 1: Build a real session**

Launch the app from the repo root (`saved/` and `./assets/` resolve against CWD):

```bash
.venv/bin/python main.py
```

Open `saved/gs.json`. Then `Session → New Session`, and:

1. `Session → Capture State` — captures the graph as state 0.
2. Add a shader node, wire it in, `Capture State` again.
3. Repeat until you have **at least 8 states** and **at least 12 distinct nodes** across the union.
4. `Session → Save Session`, save as `saved/verification.pnlive`.

- [ ] **Step 2: Measure session load cost**

Restart the app, then `Session → Open Session` on `saved/verification.pnlive`. Time it:

```bash
.venv/bin/python -c "
import time, json
from session.model import LiveSession
s = LiveSession.load('saved/verification.pnlive')
print('states:', len(s.states), 'union nodes:', len(s.compute_union()))
"
```

Record the union size and the wall-clock time from clicking Open to the dock populating. Expected: seconds, not minutes. **If load exceeds ~30s, stop and report** — the union model may need the background-compile fallback the spec deferred.

- [ ] **Step 3: Measure transition cost**

With the session loaded and a shader graph rendering, step through every state with the `Next ▶` button and watch the output window.

Record for each transition: whether the output visibly hitched, stuttered, or dropped frames.

**This is the plan's primary technical risk.** The design's whole claim is that transitions are free because nothing compiles. If any transition hitches, capture which state pair it was and what nodes differ between them, and report before proceeding.

- [ ] **Step 4: Verify audio triggers**

Set state 1's trigger to `{"type": "audio", "feature": "kick_count", "count": 8}` by editing `saved/verification.pnlive` directly, reload the session, press Play with audio running.

Expected: advances on the 8th kick, not before.

- [ ] **Step 5: Verify the degraded path**

Edit `saved/verification.pnlive` and corrupt one node's `op_code` to `999999`. Reload.

Expected: banner appears listing the problem with its state index; `Play` does nothing while the banner is up; `Run anyway` dismisses the banner but the affected state keeps its `⚠` marker; playback then works with that node absent.

- [ ] **Step 6: Verify propagation end to end**

Jump to state 2, change a shader parameter in the Inspector, `Session → Overwrite State`.

Expected: dialog reports how many later states will receive the change. Apply. Jump to state 5 and confirm the value carried. Then change that same parameter *only* in state 6, go back to state 2, change it again, overwrite — confirm state 6 is reported as skipped and keeps its own value.

- [ ] **Step 7: Write up results**

Create `docs/superpowers/plans/2026-08-02-live-session-verification.md` recording: union size, load time, per-transition hitch observations, and the outcome of steps 4–6. State plainly whether transitions were hitch-free.

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/plans/2026-08-02-live-session-verification.md
git commit -m "docs: record live session verification results"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Data model, `.pnlive` format, version 1 | 2 |
| Union derived, not stored | 2 (`compute_union`), 4 (instantiation) |
| Trigger forms (manual, counter, threshold) | 1 |
| Counter features restricted to the three real counters | 1, 3 |
| Session load sequence | 4 |
| Advancing: params, rewire, single eval | 5 |
| `restore_window_size=False` | 5 |
| All-or-nothing transitions | 5 |
| `goTo` idempotent, backs next/prev/jump | 5 |
| Trigger evaluation on the audio timer | 6 |
| Manual next always works | 6 |
| Capture / overwrite / delete / move / rename | 2 (model), 9 (menu) |
| Jump pauses playback | 9 (`onStateActivated`) |
| Propagation: params, conditional skip, preview | 7 |
| Propagation: nodes and edges | 8 |
| Propagation forward-only, opt-in per overwrite | 7, 9 |
| Validation pass, all categories, one banner | 3, 9 |
| Blocking banner, Run anyway, persistent markers | 9 |
| Malformed/unknown version refuses to open | 2, 9 |
| No modals during playback (status callback) | 5, 6, 9 |
| Atomic session save | 2 |
| Dock, menu, transport, single subwindow | 9 |
| Manual perf verification | 10 |

No gaps.

**Known deviation:** the spec says `SessionPlayer.load` reports GLSL-compile failures as findings. The implementation gets these via `scene.deserialization_errors`, which carries no state index, so those findings use `state_index = -1` and the dock renders them as "session load" rather than marking a specific state. Static failures (unregistered op_code) *do* carry a state index, so the common case still marks states correctly.

**Type consistency:** `Finding(state_index, category, message)` is constructed identically in Tasks 3 and 4 and consumed in Task 9. `PropagationOutcome.applied` holds `(state_index, ParamChange)` in Task 7 and `(state_index, str)` in Task 8 — deliberate, and Task 9 only counts `len(...)` on the structural one and only unpacks three-tuples from `skipped`, which is params-only.

**Placeholder scan:** clean. Every code step contains runnable code; every test step contains real assertions.
