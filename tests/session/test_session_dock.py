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

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QFileDialog, QMainWindow, QMenu, QMessageBox

import program.program_conf  # noqa: F401  (breaks the import cycle, see tests/serialization/test_save_load.py)
from gui.patanode import PataNode
from gui.widgets.session_dock import QDMSessionDock
from session.model import LiveSession, SessionState
from session.player import SessionPlayer
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
    # _sessionStatus goes through statusBar(), which needs the QMainWindow
    # this stub deliberately skips -- same category of stub as addDockWidget.
    window._sessionStatus = lambda message: None
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
    window.onSessionDelete = lambda: None
    window.onSessionDeleteAt = lambda index: None

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


def plain_node(nid):
    """A minimal node dict the `scene` fixture can deserialize (plain Node)."""
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


def make_delete_window(scene, names):
    """A window driving a *real* SessionPlayer over `names`, sitting on state 0.

    Deletion has to be asserted through real behaviour -- which state the
    player ends up on, what the session holds -- so this uses a real player
    and the real Scene fixture rather than StubPlayer.
    """
    states = [
        SessionState(name, {"type": "manual"}, make_scene(nodes=[plain_node(i + 1)]))
        for i, name in enumerate(names)
    ]
    player = SessionPlayer(scene)
    player.load(LiveSession(states=states), {100}, set())
    player.goTo(0)

    window = make_session_window(StubLiveEditor(scene))
    window.session_player = player
    return window, player


def _destructive_button(box):
    """Qt lays buttons out by role, not insertion order, so the confirming
    button is found by its role rather than by position in buttons()."""
    return next(
        button
        for button in box.buttons()
        if box.buttonRole(button) == QMessageBox.DestructiveRole
    )


def _click_delete(monkeypatch, confirm):
    """Answer the delete confirmation with Delete (confirm) or Cancel."""
    _allow_message_box_with_stub_parent(monkeypatch)
    monkeypatch.setattr(QMessageBox, "exec_", lambda self: None)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: (
            _destructive_button(self) if confirm else self.button(QMessageBox.Cancel)
        ),
    )


def test_delete_state_removes_the_current_state(qapp, scene, monkeypatch):
    """The gap found during the first real session: a node deleted from the
    graph left a captured state broken, with no way to remove that state
    short of hand-editing the .pnlive.
    """
    window, player = make_delete_window(scene, ["a", "b", "c"])
    player.goTo(1)
    _click_delete(monkeypatch, confirm=True)

    window.onSessionDelete()

    assert [s.name for s in player.session.states] == ["a", "c"]


def test_delete_state_shows_the_state_that_took_its_place(qapp, scene, monkeypatch):
    """Deleting state 1 of a,b,c leaves c at index 1 -- and the scene must
    actually be showing c, not still rendering the deleted b.
    """
    window, player = make_delete_window(scene, ["a", "b", "c"])
    player.goTo(1)
    _click_delete(monkeypatch, confirm=True)

    window.onSessionDelete()

    assert player.current_index == 1
    assert player.session.states[1].name == "c"


def test_delete_the_last_state_in_the_list_falls_back_to_the_previous(
    qapp, scene, monkeypatch
):
    """Nothing shifts into the tail position, so the index has to step back
    rather than point one past the end.
    """
    window, player = make_delete_window(scene, ["a", "b", "c"])
    player.goTo(2)
    _click_delete(monkeypatch, confirm=True)

    window.onSessionDelete()

    assert player.current_index == 1
    assert player.session.states[1].name == "b"


def test_delete_the_only_state_leaves_no_current_state(qapp, scene, monkeypatch):
    window, player = make_delete_window(scene, ["only"])
    _click_delete(monkeypatch, confirm=True)

    window.onSessionDelete()

    assert player.session.states == []
    assert player.current_index == -1


def test_delete_state_cancelled_keeps_the_state(qapp, scene, monkeypatch):
    """There is no session-level undo (spec), so Cancel must be honest."""
    window, player = make_delete_window(scene, ["a", "b", "c"])
    player.goTo(1)
    _click_delete(monkeypatch, confirm=False)

    window.onSessionDelete()

    assert [s.name for s in player.session.states] == ["a", "b", "c"]
    assert player.current_index == 1


def test_delete_leaves_no_dangling_index_if_the_next_state_will_not_load(
    qapp, scene, monkeypatch
):
    """States get deleted precisely because they are broken, so the state
    that shifts into place may be broken too. goTo is all-or-nothing and
    leaves current_index alone when it fails, which after a deletion would
    leave it addressing a state that no longer exists -- tick() reads
    states[current_index] at 60 Hz and would raise IndexError mid-set.
    """
    window, player = make_delete_window(scene, ["a", "b", "c"])
    player.goTo(2)
    _click_delete(monkeypatch, confirm=True)
    monkeypatch.setattr(player, "goTo", lambda index: False)

    window.onSessionDelete()

    assert len(player.session.states) == 2
    assert player.current_index < len(player.session.states)


def _right_click_state(dock, monkeypatch, row, choose_delete=True):
    """Drive the state list's context menu on `row`.

    Goes through customContextMenuRequested rather than calling the handler
    directly, so dropping the connect() in the dock fails these tests --
    calling onStateContextMenu() by hand leaves that line unguarded.

    itemAt() is stubbed because it resolves a pixel position against the
    list's geometry -- irrelevant here and unreliable offscreen. The menu
    itself is built for real; exec_ returns the chosen action.
    """
    item = dock.state_list.item(row)
    monkeypatch.setattr(dock.state_list, "itemAt", lambda point: item)
    monkeypatch.setattr(
        QMenu, "exec_", lambda self, *args: self.actions()[0] if choose_delete else None
    )
    dock.state_list.customContextMenuRequested.emit(QPoint(0, 0))


def test_state_list_asks_for_a_custom_context_menu(qapp):
    """Without CustomContextMenu the widget never emits
    customContextMenuRequested and a right-click falls through to Qt's
    default menu -- the signal-based tests below cannot see that.
    """
    assert QDMSessionDock().state_list.contextMenuPolicy() == Qt.CustomContextMenu


def test_right_click_delete_removes_the_state_that_was_clicked(
    qapp, scene, monkeypatch
):
    """Not the current state -- the one under the cursor."""
    window, player = make_delete_window(scene, ["a", "b", "c"])
    window.session_widget.setPlayer(player)
    _click_delete(monkeypatch, confirm=True)

    _right_click_state(window.session_widget, monkeypatch, row=2)

    assert [s.name for s in player.session.states] == ["a", "b"]


def test_deleting_a_state_after_the_current_one_does_not_reload(
    qapp, scene, monkeypatch
):
    """The displayed graph is untouched by removing a later state, so there
    is nothing to transition to -- goTo would be a pointless rewire, and on
    real shader nodes a pointless render pull.
    """
    window, player = make_delete_window(scene, ["a", "b", "c"])
    player.goTo(0)
    window.session_widget.setPlayer(player)
    _click_delete(monkeypatch, confirm=True)
    monkeypatch.setattr(
        player, "goTo", lambda index: pytest.fail("must not re-enter a state")
    )

    _right_click_state(window.session_widget, monkeypatch, row=2)

    assert player.current_index == 0


def test_deleting_a_state_before_the_current_one_keeps_the_same_state_showing(
    qapp, scene, monkeypatch
):
    """Everything after the removed state shifts down one, so the index has
    to follow or the dock marker lands on the wrong row -- but the graph on
    screen is still the same state, so again no reload.
    """
    window, player = make_delete_window(scene, ["a", "b", "c"])
    player.goTo(2)
    window.session_widget.setPlayer(player)
    _click_delete(monkeypatch, confirm=True)
    monkeypatch.setattr(
        player, "goTo", lambda index: pytest.fail("must not re-enter a state")
    )

    _right_click_state(window.session_widget, monkeypatch, row=0)

    assert player.current_index == 1
    assert player.session.states[1].name == "c"


def test_right_click_delete_cancelled_keeps_the_state(qapp, scene, monkeypatch):
    """The confirmation applies to this path too, not just the button."""
    window, player = make_delete_window(scene, ["a", "b", "c"])
    window.session_widget.setPlayer(player)
    _click_delete(monkeypatch, confirm=False)

    _right_click_state(window.session_widget, monkeypatch, row=2)

    assert [s.name for s in player.session.states] == ["a", "b", "c"]


def test_delete_button_deletes_the_current_state(qapp, scene, monkeypatch):
    """Drives the real QPushButton through the real createSessionDock, so
    deleting either production wiring line fails this -- same reason
    test_capture_button_captures_a_state does.
    """
    window, player = make_delete_window(scene, ["a", "b"])
    window.session_widget.setPlayer(player)
    _click_delete(monkeypatch, confirm=True)

    window.session_widget.btn_delete.click()

    assert [s.name for s in player.session.states] == ["b"]


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
