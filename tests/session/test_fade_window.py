"""The Fade editor window and the dock button that opens it."""

import pytest
from PyQt5.QtCore import Qt

import program.program_conf  # noqa: F401  (breaks the import cycle, see test_session_dock.py)
from gui.widgets.fade_window import QDMFadeWindow
from gui.widgets.session_dock import QDMSessionDock
from session.fade import FadeParam, FadeSpec
from session.model import LiveSession, SessionState


def gpu_node(nid, title, uniforms):
    return {
        "id": nid,
        "title": title,
        "gpu_adaptable_parameters": {
            "program": {
                name: {"eval_function": {"value": value}}
                for name, value in uniforms.items()
            }
        },
    }


def make_session(prev_uniforms, next_uniforms, fade=None, title="Blend"):
    return LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                {"nodes": [gpu_node(1, title, prev_uniforms)], "edges": []},
            ),
            SessionState(
                "b",
                {"type": "manual"},
                {"nodes": [gpu_node(1, title, next_uniforms)], "edges": []},
                fade=fade,
            ),
        ]
    )


class StubPlayer:
    def __init__(self, session, current_index=0):
        self.session = session
        self.current_index = current_index
        self.is_playing = False


def param_items(window):
    items = []
    for i in range(window.tree.topLevelItemCount()):
        node_item = window.tree.topLevelItem(i)
        for j in range(node_item.childCount()):
            items.append(node_item.child(j))
    return items


def by_uniform(window):
    return {item.data(0, Qt.UserRole)["uniform"]: item for item in param_items(window)}


@pytest.fixture
def window(qapp):
    return QDMFadeWindow()


# -- population -----------------------------------------------------------


def test_it_lists_every_common_uniform_not_only_the_changed_ones(window):
    """A Blend node stores the same baseBlend in both states -- listing only
    what differs would hide the one knob worth sweeping."""
    session = make_session(
        {"baseBlend": "0.5", "bias": "x"}, {"baseBlend": "0.5", "bias": "x*2"}
    )
    window.setTarget(StubPlayer(session), 1)

    assert sorted(by_uniform(window)) == ["baseBlend", "bias"]


def test_differing_params_are_preticked_and_marked(window):
    session = make_session(
        {"baseBlend": "0.5", "bias": "x"}, {"baseBlend": "0.5", "bias": "x*2"}
    )
    window.setTarget(StubPlayer(session), 1)
    items = by_uniform(window)

    assert items["bias"].checkState(0) == Qt.Checked
    assert "*" in items["bias"].text(0)
    assert items["baseBlend"].checkState(0) == Qt.Unchecked
    assert "*" not in items["baseBlend"].text(0)


def test_the_first_state_has_nothing_to_fade_from(window):
    """A fade eases from the outgoing values, and state 0 has no
    predecessor to author the pair against."""
    session = make_session({"speed": "1"}, {"speed": "2"})
    window.setTarget(StubPlayer(session), 0)

    assert window.tree.topLevelItemCount() == 0
    assert not window.btn_apply.isEnabled()
    assert "first state" in window.header.text()


def test_an_existing_fade_is_loaded_back(window):
    spec = FadeSpec(
        3.5,
        "linear",
        [FadeParam(1, "program", "baseBlend", from_value="0", to_value="1")],
    )
    session = make_session(
        {"baseBlend": "0.5", "bias": "x"},
        {"baseBlend": "0.5", "bias": "x*2"},
        fade=spec,
    )
    window.setTarget(StubPlayer(session), 1)
    items = by_uniform(window)

    assert window.duration.value() == pytest.approx(3.5)
    assert window.curve.currentText() == "linear"
    # The saved choice wins over the differs heuristic in both directions.
    assert items["baseBlend"].checkState(0) == Qt.Checked
    assert items["bias"].checkState(0) == Qt.Unchecked
    assert window.tree.itemWidget(items["baseBlend"], 1).text() == "0"
    assert window.tree.itemWidget(items["baseBlend"], 2).text() == "1"


# -- applying -------------------------------------------------------------


def test_apply_writes_a_spec_onto_the_target_state(window):
    session = make_session({"speed": "1"}, {"speed": "2"})
    window.setTarget(StubPlayer(session), 1)
    window.duration.setValue(2.5)
    window.curve.setCurrentText("linear")

    window.onApply()

    fade = session.states[1].fade
    assert fade.duration == pytest.approx(2.5)
    assert fade.curve == "linear"
    assert [p.uniform for p in fade.params] == ["speed"]


def test_untouched_endpoints_stay_null(window):
    """Null means "resolve live at switch time", which is what keeps a fade
    working no matter which state you jumped from. Baking the state values
    in would silently pin it to one path."""
    session = make_session({"speed": "1"}, {"speed": "2"})
    window.setTarget(StubPlayer(session), 1)

    window.onApply()

    param = session.states[1].fade.params[0]
    assert param.from_value is None and param.to_value is None


def test_an_edited_endpoint_is_persisted(window):
    """Typing 0 -> 1 on a parameter both states share is how a Blend node
    becomes a crossfade."""
    session = make_session({"baseBlend": "0.5"}, {"baseBlend": "0.5"})
    window.setTarget(StubPlayer(session), 1)
    item = by_uniform(window)["baseBlend"]
    item.setCheckState(0, Qt.Checked)
    window.tree.itemWidget(item, 1).setText("0")
    window.tree.itemWidget(item, 2).setText("1")

    window.onApply()

    param = session.states[1].fade.params[0]
    assert param.from_value == "0"
    assert param.to_value == "1"


def test_unticking_everything_clears_the_fade(window):
    """Not an empty FadeSpec: SessionPlayer treats None as "hard cut", and
    the dock's marker keys off it too."""
    spec = FadeSpec(2.0, "linear", [FadeParam(1, "program", "speed")])
    session = make_session({"speed": "1"}, {"speed": "2"}, fade=spec)
    window.setTarget(StubPlayer(session), 1)
    for item in param_items(window):
        item.setCheckState(0, Qt.Unchecked)

    window.onApply()

    assert session.states[1].fade is None


def test_apply_notifies_its_owner(window):
    session = make_session({"speed": "1"}, {"speed": "2"})
    window.setTarget(StubPlayer(session), 1)
    calls = []
    window.on_applied = lambda: calls.append(1)

    window.onApply()

    assert calls == [1], "the dock's fade marker has to refresh after Apply"


def test_apply_with_no_target_does_nothing(window):
    window.setTarget(None, -1)
    window.onApply()


# -- the dock button ------------------------------------------------------


def test_the_fade_button_opens_the_editor_on_the_selected_state(qapp):
    """Drives the real button rather than asserting a handler exists."""
    dock = QDMSessionDock()
    session = make_session({"speed": "1"}, {"speed": "2"})
    dock.setPlayer(StubPlayer(session))
    dock.state_list.setCurrentRow(1)

    dock.btn_fade.click()

    assert dock._fade_window is not None
    assert dock._fade_window.index == 1
    assert sorted(by_uniform(dock._fade_window)) == ["speed"]


def test_the_fade_window_is_reused_not_rebuilt(qapp):
    dock = QDMSessionDock()
    dock.setPlayer(StubPlayer(make_session({"speed": "1"}, {"speed": "2"})))
    dock.state_list.setCurrentRow(1)

    dock.btn_fade.click()
    first = dock._fade_window
    dock.btn_fade.click()

    assert dock._fade_window is first


def test_the_fade_button_is_inert_without_a_session(qapp):
    dock = QDMSessionDock()
    dock.btn_fade.click()
    assert dock._fade_window is None


def test_dropping_the_player_closes_the_editor(qapp):
    """The editor writes onto the session's states; it must not outlive it."""
    dock = QDMSessionDock()
    dock.setPlayer(StubPlayer(make_session({"speed": "1"}, {"speed": "2"})))
    dock.state_list.setCurrentRow(1)
    dock.btn_fade.click()
    assert dock._fade_window is not None

    dock.onFixAndReload()

    assert dock._fade_window is None


def test_the_state_list_shows_which_states_fade(qapp):
    """Visible at a glance during a set, next to the trigger summary."""
    spec = FadeSpec(2.0, "linear", [FadeParam(1, "program", "speed")])
    dock = QDMSessionDock()
    dock.setPlayer(StubPlayer(make_session({"speed": "1"}, {"speed": "2"}, fade=spec)))

    assert "~2s" in dock.state_list.item(1).text()
    assert "~" not in dock.state_list.item(0).text()


def test_only_nodes_with_something_ticked_start_expanded(window):
    """A real state pair is 22 nodes and 125 parameters with 3 of them
    differing (saved/physarum_depth.pnlive). Expanding all of it buries the
    rows worth looking at."""
    session = LiveSession(
        states=[
            SessionState(
                "a",
                {"type": "manual"},
                {
                    "nodes": [
                        gpu_node(1, "Quiet", {"speed": "1"}),
                        gpu_node(2, "Changed", {"speed": "1"}),
                    ],
                    "edges": [],
                },
            ),
            SessionState(
                "b",
                {"type": "manual"},
                {
                    "nodes": [
                        gpu_node(1, "Quiet", {"speed": "1"}),
                        gpu_node(2, "Changed", {"speed": "9"}),
                    ],
                    "edges": [],
                },
            ),
        ]
    )
    window.setTarget(StubPlayer(session), 1)

    expanded = {
        window.tree.topLevelItem(i)
        .text(0)
        .split("  ")[0]: window.tree.topLevelItem(i)
        .isExpanded()
        for i in range(window.tree.topLevelItemCount())
    }
    assert expanded == {"Quiet": False, "Changed": True}
