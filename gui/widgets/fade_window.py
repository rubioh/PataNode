"""Fade editor: pick which parameters ease when a state is entered.

A floating window rather than a dock, following PalettePreviewWindow
(program/colors/value_gradient/palette_preview.py): created lazily once and
then shown/hidden, never rebuilt. Unlike that one it has no refresh timer --
this is an editor, not a live view, so it only repopulates on setTarget.

All the dict-walking lives in session/fade.py:fade_candidates. This file is
only the widget.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from session.fade import (
    CURVES,
    DEFAULT_CURVE,
    DEFAULT_DURATION,
    FadeParam,
    FadeSpec,
    fade_candidates,
)

PARAM_ROLE = Qt.UserRole


class QDMFadeWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fade")
        self.resize(560, 420)

        self.player = None
        self.index = -1
        # Set by the owner (QDMSessionDock) so applying a fade refreshes the
        # state list's duration marker without this window holding a
        # reference back to the dock.
        self.on_applied = None

        layout = QVBoxLayout()

        self.header = QLabel("")
        self.header.setWordWrap(True)
        layout.addWidget(self.header)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Parameter", "From", "To"])
        self.tree.setColumnWidth(0, 260)
        layout.addWidget(self.tree)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Duration"))
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.05, 120.0)
        self.duration.setSingleStep(0.25)
        self.duration.setSuffix(" s")
        self.duration.setValue(DEFAULT_DURATION)
        controls.addWidget(self.duration)

        controls.addWidget(QLabel("Curve"))
        self.curve = QComboBox()
        self.curve.addItems(sorted(CURVES))
        self.curve.setCurrentText(DEFAULT_CURVE)
        controls.addWidget(self.curve)

        controls.addStretch()
        self.btn_apply = QPushButton("Apply")
        self.btn_close = QPushButton("Close")
        controls.addWidget(self.btn_apply)
        controls.addWidget(self.btn_close)
        layout.addLayout(controls)

        self.setLayout(layout)

        self.btn_apply.clicked.connect(self.onApply)
        self.btn_close.clicked.connect(self.close)

    # -- population -------------------------------------------------------

    def setTarget(self, player, index: int) -> None:
        """Point the window at "the fade into state `index`"."""
        self.player = player
        self.index = index
        self.tree.clear()

        states = (
            player.session.states
            if player is not None and player.session is not None
            else []
        )
        if not (0 <= index < len(states)):
            self._setEmpty("Select a state to edit its fade.")
            return

        if index == 0:
            # A fade eases from the outgoing state's values, and the first
            # state has nothing before it. It still fades when reached from
            # a later state via Prev, but there is no pair to author against.
            self._setEmpty(
                "'%s' is the first state — there is no previous state to fade from."
                % (states[index].name or "state 0")
            )
            return

        self.setWindowTitle("Fade — %s" % (states[index].name or "state %d" % index))
        self.header.setText(
            "Fade: %s  →  %s\n"
            "Ticked parameters ease over the duration; the rest cut instantly. "
            "'*' marks the ones that differ between the two states. Edit From/To "
            "to sweep a parameter the two states happen to share — that is how a "
            "Blend node becomes a crossfade."
            % (
                states[index - 1].name or "state %d" % (index - 1),
                states[index].name or "state %d" % index,
            )
        )
        self._setControlsEnabled(True)

        existing = states[index].fade
        # None means "this state has never been authored", which is when the
        # differs heuristic gets to pre-tick rows. Once a fade exists it is
        # an explicit decision -- re-ticking a differing parameter the user
        # deliberately left out would quietly undo it on the next Apply.
        selected = None
        if existing is not None:
            selected = {param.key: param for param in existing.params}
            self.duration.setValue(existing.duration)
            self.curve.setCurrentText(existing.curve)

        for candidate in fade_candidates(states[index - 1].scene, states[index].scene):
            self._addNode(candidate, selected)

    def _setEmpty(self, message: str) -> None:
        self.header.setText(message)
        self._setControlsEnabled(False)

    def _setControlsEnabled(self, enabled: bool) -> None:
        for widget in (self.tree, self.duration, self.curve, self.btn_apply):
            widget.setEnabled(enabled)

    def _addNode(self, candidate: dict, selected: dict) -> None:
        node_item = QTreeWidgetItem(self.tree)
        differing = sum(1 for p in candidate["params"] if p["differs"])
        node_item.setText(
            0,
            "%s  (id %s)%s"
            % (
                candidate["title"],
                candidate["node_id"],
                "   %d differ" % differing if differing else "",
            ),
        )
        # AutoTristate makes the node row follow its children, so ticking a
        # whole node is one click and the row shows partial selection.
        node_item.setFlags(
            node_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate
        )
        node_item.setCheckState(0, Qt.Unchecked)

        for param in candidate["params"]:
            self._addParam(node_item, candidate["node_id"], param, selected)

        # Expand only what is already ticked. A real pair of states runs to
        # 22 nodes and 125 parameters with 3 of them differing (measured on
        # saved/physarum_depth.pnlive) -- expanding all of it buries the rows
        # worth looking at. Everything else is one click away.
        node_item.setExpanded(
            any(
                node_item.child(i).checkState(0) == Qt.Checked
                for i in range(node_item.childCount())
            )
        )

    def _addParam(self, node_item, node_id, param: dict, selected: dict) -> None:
        item = QTreeWidgetItem(node_item)
        item.setText(0, param["uniform"] + ("  *" if param["differs"] else ""))
        if param["differs"]:
            item.setToolTip(0, "Differs between the two states")
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

        key = (node_id, param["program"], param["uniform"])
        chosen = selected.get(key) if selected is not None else None
        item.setData(
            0,
            PARAM_ROLE,
            {
                "node_id": node_id,
                "program": param["program"],
                "uniform": param["uniform"],
                # The state values, kept so onApply can tell an edited
                # endpoint from an untouched one and leave the latter null.
                "state_from": param["from"],
                "state_to": param["to"],
            },
        )

        if selected is not None:
            # Authored already: the saved selection is the whole truth.
            checked = chosen is not None
        else:
            # Never authored: differing parameters are the ones worth easing,
            # so pre-tick them and leave the rest as opt-in.
            checked = param["differs"]
        item.setCheckState(0, Qt.Checked if checked else Qt.Unchecked)

        from_edit = QLineEdit(
            chosen.from_value
            if chosen is not None and chosen.from_value is not None
            else param["from"]
        )
        to_edit = QLineEdit(
            chosen.to_value
            if chosen is not None and chosen.to_value is not None
            else param["to"]
        )
        self.tree.setItemWidget(item, 1, from_edit)
        self.tree.setItemWidget(item, 2, to_edit)

    # -- applying ---------------------------------------------------------

    def onApply(self) -> None:
        state = self._currentState()
        if state is None:
            return

        params = []
        for item in self._paramItems():
            if item.checkState(0) != Qt.Checked:
                continue
            meta = item.data(0, PARAM_ROLE)
            from_text = self.tree.itemWidget(item, 1).text()
            to_text = self.tree.itemWidget(item, 2).text()
            params.append(
                FadeParam(
                    meta["node_id"],
                    meta["program"],
                    meta["uniform"],
                    # Only persist an endpoint the user actually changed.
                    # Left alone, it stays null and resolves live at switch
                    # time, which is what keeps a fade independent of which
                    # state you arrived from.
                    from_value=(from_text if from_text != meta["state_from"] else None),
                    to_value=(to_text if to_text != meta["state_to"] else None),
                )
            )

        state.fade = (
            FadeSpec(self.duration.value(), self.curve.currentText(), params)
            if params
            else None
        )

        if self.on_applied is not None:
            self.on_applied()

    def _currentState(self):
        if self.player is None or self.player.session is None:
            return None
        states = self.player.session.states
        if not (0 <= self.index < len(states)):
            return None
        return states[self.index]

    def _paramItems(self):
        for i in range(self.tree.topLevelItemCount()):
            node_item = self.tree.topLevelItem(i)
            for j in range(node_item.childCount()):
                yield node_item.child(j)
