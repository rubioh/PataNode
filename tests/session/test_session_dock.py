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

from PyQt5.QtWidgets import QFileDialog, QMainWindow, QMessageBox

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


def _allow_message_box_with_stub_parent(monkeypatch):
    """onSessionOverwrite's dialog now constructs a real QMessageBox(self).

    `node` in these tests is a PataNode built via __new__ (see
    make_patanode below), which skips QMainWindow.__init__ entirely -- it
    is not a real QWidget, so passing it as a Qt parent raises. Production
    code always has a real, fully-initialized PataNode here; only the test
    stub needs this, so the parent is dropped rather than the real
    onSessionOverwrite code being changed to accommodate the test.
    """
    real_init = QMessageBox.__init__

    def fake_init(self, *args, **kwargs):
        real_init(self)

    monkeypatch.setattr(QMessageBox, "__init__", fake_init)


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


def test_overwrite_reports_structural_skip_even_with_no_applied_changes(
    monkeypatch, qapp
):
    """Finding 1.

    State 0's edge e1 is deleted while editing. State 1 already rewired
    that same edge (different endpoint), so propagate_structure must skip
    it rather than clobbering the rewire. Nothing else changes -- applied
    counts are all zero -- so the old code's `total == 0 and not
    preview_params.skipped` early return would have suppressed the dialog
    entirely, silently dropping the one thing the performer needed to see.

    onSessionOverwrite now builds the confirmation dialog by hand (a plain
    QMessageBox with addButton()) instead of the QMessageBox.question()
    one-liner, so the exec_()/clickedButton() pair is stubbed instead of
    the static convenience method -- addButton, setText, etc. all run for
    real against a live QApplication (the `qapp` fixture).
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

    _allow_message_box_with_stub_parent(monkeypatch)

    captured = {}

    def fake_exec(self):
        captured["text"] = self.text()

    monkeypatch.setattr(QMessageBox, "exec_", fake_exec)
    # Simulate the user clicking the standard Cancel button.
    monkeypatch.setattr(
        QMessageBox, "clickedButton", lambda self: self.button(QMessageBox.Cancel)
    )

    node.onSessionOverwrite()

    assert "text" in captured, (
        "the confirmation dialog must appear when a structural change is "
        "skipped, even if nothing was applied"
    )
    assert "removed edge e1" in captured["text"]
    assert "state rewired this edge" in captured["text"]


def test_overwrite_cancel_does_not_commit_the_overwrite(monkeypatch, qapp):
    """Finding (Important 6): Cancel must be honest.

    The previous implementation called player.session.overwrite(index,
    current) *before* the dialog was shown, so clicking Cancel only ever
    skipped propagation -- the state had already been replaced, with no
    session-level undo to recover it (spec: "No session-level undo").

    This asserts the state itself is untouched after Cancel -- not just
    that the dialog appeared.
    """
    baseline_scene = make_scene(nodes=[{"id": 1, "op_code": 100}])
    edited_scene = make_scene(nodes=[{"id": 1, "op_code": 100}, {"id": 2}])
    # A later state that would make propagation non-trivial (so the dialog
    # actually appears rather than taking the "nothing to propagate" path).
    later_scene = make_scene(nodes=[{"id": 1, "op_code": 100}])

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

    _allow_message_box_with_stub_parent(monkeypatch)
    monkeypatch.setattr(QMessageBox, "exec_", lambda self: None)
    monkeypatch.setattr(
        QMessageBox, "clickedButton", lambda self: self.button(QMessageBox.Cancel)
    )

    node.onSessionOverwrite()

    assert (
        session.states[0].scene == baseline_scene
    ), "Cancel must not commit the overwrite of the current state"


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


def test_known_opcodes_includes_graph_container():
    """IMPORTANT 3: get_class_from_opcode (node/node_conf.py:60-70) accepts
    GRAPH_CONTAINER_OPCODE alongside SHADER_NODES/AUDIO_NODES, but
    _knownOpcodes previously only unioned the latter two. Any session
    containing a graph-container node would raise a spurious "unregistered
    op_code" finding, showing the blocking banner on a perfectly valid
    session.
    """
    from node.node_conf import GRAPH_CONTAINER_OPCODE

    assert GRAPH_CONTAINER_OPCODE in PataNode._knownOpcodes()


def test_fix_and_reload_clears_the_owning_windows_session_player(qapp):
    """Minor: onFixAndReload dropped the dock's own `.player` but left
    PataNode.session_player pointing at the same (now-orphaned) player, so
    app.py's 60 Hz audio tick kept driving a session with no visible
    transport. QDMSessionDock has no reference to its owning PataNode, so
    the owner wires a callback (on_player_dropped) at dock-creation time;
    this test stands in for that owner.
    """
    dock = QDMSessionDock()
    session = LiveSession(states=[SessionState("a", {"type": "manual"}, make_scene())])
    player = StubPlayer(session, current_index=0)
    dock.setPlayer(player)

    main_window = {"session_player": player}
    dock.on_player_dropped = lambda: main_window.__setitem__("session_player", None)

    dock.onFixAndReload()

    assert dock.player is None
    assert main_window["session_player"] is None


def test_capture_names_state_with_its_zero_based_index():
    """Minor: the captured state's name must match the 0-based index the
    dock actually displays it at. The old code named it "state %d" %
    (len(states) + 1) -- computed *before* insertion and 1-based -- which
    is both off by one against the dock's numbering and wrong whenever
    after_index inserts the state anywhere but the very end.
    """
    session = LiveSession(
        states=[SessionState("existing", {"type": "manual"}, make_scene())]
    )
    player = StubPlayer(session, current_index=0)
    player._entry = {"count_at_entry": 5}
    editor = StubEditor(make_scene(nodes=[{"id": 1}]))
    dock = StubDock()
    node = make_patanode(editor, player, dock)

    node.onSessionCapture()

    # Captured right after state 0 -> lands at index 1.
    assert player.current_index == 1
    assert session.states[1].name == "state 1"


class StubLiveEditor:
    """Stands in for PataNodeSubWindow where a *real* Scene is needed.

    onSessionNew/onSessionOpen hand editor.scene to SessionPlayer, which
    deserializes the union into it -- StubScene's serialize()-only surface
    is not enough.
    """

    def __init__(self, scene):
        self.scene = scene

    def doEvalOutputs(self):
        pass


def make_session_window(editor):
    """A PataNode with a real session dock but no QMainWindow behind it.

    addDockWidget is the only thing stubbed; see test_capture_button_captures_a_state.
    """
    window = PataNode.__new__(PataNode)
    window.session_player = None
    window.session_filename = None
    window.getCurrentNodeEditorWidget = lambda: editor
    window.addDockWidget = lambda *args: None
    window.createSessionDock()
    return window


def test_session_dock_starts_hidden(qapp):
    """The dock is meaningless until a session exists, so it must not take
    up the bottom of the window on startup -- same treatment audioDock
    already gets (gui/patanode.py:171).

    This uses a real, shown QMainWindow rather than the PataNode.__new__
    stub: isHidden() is true for any widget that was merely never shown, so
    against an unshown parent the assertion would hold with or without the
    fix and prove nothing.
    """
    window = QMainWindow()
    window._clearSessionPlayer = lambda: None
    window.onSessionCapture = lambda: None

    PataNode.createSessionDock(window)
    window.show()

    try:
        assert window.sessionDock.isHidden()
    finally:
        window.close()


def test_new_session_reveals_the_dock(qapp, scene):
    """Session -> New Session is one of the two ways a session comes into
    existence, so it is one of the two places the dock must appear.
    """
    window = make_session_window(StubLiveEditor(scene))
    window.sessionDock.hide()

    window.onSessionNew()

    assert not window.sessionDock.isHidden()


def test_open_session_reveals_the_dock(qapp, scene, monkeypatch, tmp_path):
    """The other way in. Opening also has to survive the validation banner
    path, so the dock is revealed regardless of findings.
    """
    path = tmp_path / "s.pnlive"
    LiveSession(
        states=[SessionState("state 0", {"type": "manual"}, make_scene())]
    ).save(str(path))

    window = make_session_window(StubLiveEditor(scene))
    window.sessionDock.hide()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(path), "")
    )

    window.onSessionOpen()

    assert not window.sessionDock.isHidden()


def test_capture_button_captures_a_state(qapp):
    """The dock's Capture button was created and laid out but never
    connected to anything, so it silently did nothing -- the only working
    capture was the Session -> Capture State menu action.

    This drives the whole path rather than asserting a callback exists:
    createSessionDock runs for real (so deleting its wiring line fails this
    test), the real QPushButton is clicked, and the assertion is on the
    session actually gaining a state. addDockWidget is the one thing
    stubbed -- it needs a fully initialized QMainWindow, and PataNode here
    is built via __new__ (see make_patanode).
    """
    session = LiveSession(
        states=[SessionState("existing", {"type": "manual"}, make_scene())]
    )
    player = StubPlayer(session, current_index=0)
    player._entry = None
    editor = StubEditor(make_scene(nodes=[{"id": 1}]))

    window = PataNode.__new__(PataNode)
    window.session_player = player
    window.getCurrentNodeEditorWidget = lambda: editor
    window.addDockWidget = lambda *args: None
    window.createSessionDock()
    window.session_widget.setPlayer(player)

    window.session_widget.btn_capture.click()

    assert len(session.states) == 2, "clicking Capture must append a state"
    assert session.states[1].name == "state 1"
    assert player.current_index == 1


def test_capture_resets_the_trigger_entry_baseline():
    """Minor: onSessionCapture set player.current_index directly without
    resetting player._entry, leaking a counter baseline computed for the
    previous state into the freshly captured one.
    """
    session = LiveSession(
        states=[SessionState("existing", {"type": "manual"}, make_scene())]
    )
    player = StubPlayer(session, current_index=0)
    player._entry = {"count_at_entry": 999}
    editor = StubEditor(make_scene(nodes=[{"id": 1}]))
    dock = StubDock()
    node = make_patanode(editor, player, dock)

    node.onSessionCapture()

    assert player._entry is None
