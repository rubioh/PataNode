"""Tests guarding two review findings on the Task 9 session dock/menu:

- Finding 1: `PataNode.onSessionOverwrite` only read `preview_params.skipped`
  when building the confirmation dialog, so a structural conflict (a later
  state that rewired an edge or protected a node from deletion) never
  reached the user, and the dialog was skipped entirely when the only
  outcome was a structural skip.
- Finding 2: `QDMSessionDock.warned_states` was keyed on raw list index, so
  a capture() inserted earlier in the session shifted every later index and
  made the warning marker drift onto the wrong state.
"""

from PyQt5.QtWidgets import QMessageBox

import program.program_conf  # noqa: F401  (breaks the import cycle, see tests/serialization/test_save_load.py)
from gui.patanode import PataNode
from gui.widgets.session_dock import QDMSessionDock
from session.model import LiveSession, SessionState
from session.validation import Finding


def make_scene(edges=None, nodes=None):
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": list(nodes or []),
        "edges": list(edges or []),
    }


class StubScene:
    """Stands in for Scene: onSessionOverwrite only calls .serialize()."""

    def __init__(self, data):
        self._data = data

    def serialize(self):
        return self._data


class StubEditor:
    """Stands in for PataNodeSubWindow: onSessionOverwrite only reads .scene."""

    def __init__(self, scene_data):
        self.scene = StubScene(scene_data)


class StubPlayer:
    """Stands in for SessionPlayer: onSessionOverwrite only reads these two."""

    def __init__(self, session, current_index, is_playing=False):
        self.session = session
        self.current_index = current_index
        self.is_playing = is_playing


class StubDock:
    def refresh(self):
        pass


def make_patanode(editor, player, dock):
    """A PataNode exposing only what onSessionOverwrite touches.

    Building a real PataNode/PataShadeApp pulls in a GL context, the audio
    engine, the depth engine and USB probing -- none of it relevant to this
    method. __new__ skips __init__ entirely; the three attributes/methods
    onSessionOverwrite actually reads are set by hand.
    """
    instance = PataNode.__new__(PataNode)
    instance.session_player = player
    instance.session_widget = dock
    instance.getCurrentNodeEditorWidget = lambda: editor
    return instance


def test_overwrite_reports_structural_skip_even_with_no_applied_changes(monkeypatch):
    """Finding 1.

    State 0's edge e1 is deleted while editing. State 1 already rewired
    that same edge (different endpoint), so propagate_structure must skip
    it rather than clobbering the rewire. Nothing else changes -- applied
    counts are all zero -- so the old code's `total == 0 and not
    preview_params.skipped` early return would have suppressed the dialog
    entirely, silently dropping the one thing the performer needed to see.
    """
    baseline_scene = make_scene(
        edges=[{"id": "e1", "start": "s1", "end": "s2", "edge_type": 1}]
    )
    edited_scene = make_scene(edges=[])
    later_scene = make_scene(
        edges=[{"id": "e1", "start": "s1", "end": "s3", "edge_type": 1}]
    )

    session = LiveSession(
        states=[
            SessionState("state 0", {"type": "manual"}, baseline_scene),
            SessionState("state 1", {"type": "manual"}, later_scene),
        ]
    )
    player = StubPlayer(session, current_index=0)
    editor = StubEditor(edited_scene)
    dock = StubDock()
    node = make_patanode(editor, player, dock)

    captured = {}

    def fake_question(parent, title, text, buttons):
        captured["text"] = text
        return QMessageBox.Cancel

    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))

    node.onSessionOverwrite()

    assert "text" in captured, (
        "the confirmation dialog must appear when a structural change is "
        "skipped, even if nothing was applied"
    )
    assert "removed edge e1" in captured["text"]
    assert "state rewired this edge" in captured["text"]


def test_warning_marker_survives_a_capture_inserted_before_it(qapp):
    """Finding 2.

    A finding against state 2 must keep pointing at that same state after a
    capture() inserts a new state ahead of it (shifting it to index 3), not
    at whatever state now happens to sit at index 2.
    """
    session = LiveSession(
        states=[
            SessionState("state 0", {"type": "manual"}, make_scene()),
            SessionState("state 1", {"type": "manual"}, make_scene()),
            SessionState("state 2 (warned)", {"type": "manual"}, make_scene()),
        ]
    )
    player = StubPlayer(session, current_index=0)
    warned_state = session.states[2]

    dock = QDMSessionDock()
    dock.setPlayer(player)
    dock.showFindings([Finding(2, "node", "uses unregistered op_code")])

    assert warned_state in dock.warned_states

    # Insert a new state right after state 0: old index 1 -> 2, old index 2
    # (the warned one) -> 3.
    session.capture(make_scene(), "inserted", after_index=0)
    dock.refresh()

    assert dock.state_list.item(3).text().endswith("⚠"), (
        "the state that was actually warned must keep its marker at its " "new position"
    )
    assert not dock.state_list.item(2).text().endswith("⚠"), (
        "the state that only inherited the old numeric index must not "
        "inherit the marker too"
    )
