"""Live session dock: state list, transport, and the validation banner."""

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class QDMSessionDock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = None
        self.warned_states = set()
        # Built on first use and then shown/hidden, like a node's preview
        # window (node/shader_node_base.py:setPreviewWindowVisible).
        self._fade_window = None
        # Set by the owner (PataNode.createSessionDock) so onFixAndReload
        # can clear the main window's reference too, not just the dock's --
        # otherwise PataNode.session_player keeps pointing at the dropped
        # player and app.py's 60 Hz audio tick keeps driving a session with
        # no visible transport.
        self.on_player_dropped = None
        # Same reason: capturing a state needs the active editor's scene,
        # which only the main window can reach. Set by the owner
        # (PataNode.createSessionDock) so the dock's Capture button and the
        # Session -> Capture State menu action run the same code.
        self.on_capture_requested = None

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
        self.btn_fade = QPushButton("Fade…")
        for button in (
            self.btn_prev,
            self.btn_play,
            self.btn_next,
            self.btn_capture,
            self.btn_fade,
        ):
            transport.addWidget(button)
        layout.addLayout(transport)

        self.setLayout(layout)

        self.btn_prev.clicked.connect(self.onPrev)
        self.btn_next.clicked.connect(self.onNext)
        self.btn_play.clicked.connect(self.onTogglePlay)
        self.btn_run_anyway.clicked.connect(self.onRunAnyway)
        self.btn_reload.clicked.connect(self.onFixAndReload)
        self.btn_capture.clicked.connect(self.onCapture)
        self.btn_fade.clicked.connect(self.onFade)

    def setPlayer(self, player):
        self.player = player
        self.refresh()

    def showFindings(self, findings):
        """Blocking banner. Playback cannot start until it is dismissed.

        Markers are keyed on the SessionState objects themselves, not their
        list index -- a later capture() shifts every following index, and a
        marker that remembered "index 2" would silently point at whatever
        state ends up there instead of the one that was actually warned.
        """
        states = (
            self.player.session.states
            if self.player is not None and self.player.session is not None
            else []
        )
        self.warned_states = {
            states[f.state_index] for f in findings if 0 <= f.state_index < len(states)
        }

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

    def onFixAndReload(self):
        """Drop the loaded session so the fixed file must be reopened.

        The dock has no filename of its own (only the main window does), so
        there is no honest "reload from disk" it can perform by itself.
        Dropping the player is the truthful alternative to a button that
        looks like it reloads but silently does nothing: it forces the next
        step to be an explicit Session -> Open Session on the corrected file.
        """
        self.banner.hide()
        self.banner_buttons.hide()
        self.warned_states = set()
        self.player = None
        self.closeFadeWindow()
        if self.on_player_dropped is not None:
            self.on_player_dropped()
        self.refresh()

    def refresh(self):
        self.state_list.clear()
        if self.player is None or self.player.session is None:
            return

        for index, state in enumerate(self.player.session.states):
            label = "%2d  %s   [%s]%s" % (
                index,
                state.name or "(unnamed)",
                self._trigger_summary(state.trigger),
                self._fade_summary(state),
            )
            if index == self.player.current_index:
                label = "▶ " + label
            else:
                label = "   " + label
            if state in self.warned_states:
                label += "   ⚠"

            item = QListWidgetItem(label)
            self.state_list.addItem(item)

        self.btn_play.setText("❚❚ Pause" if self.player.is_playing else "▶ Play")

    @staticmethod
    def _fade_summary(state):
        """Which states ease in, visible at a glance during a set."""
        fade = getattr(state, "fade", None)
        if fade is None or not fade.params:
            return ""
        return "  ~%gs ×%d" % (fade.duration, len(fade.params))

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

    def onCapture(self):
        if self.on_capture_requested is not None:
            self.on_capture_requested()

    def onFade(self):
        """Edit the fade into whichever state is selected in the list."""
        if self.player is None or self.player.session is None:
            return

        index = self.state_list.currentRow()
        if index < 0:
            index = max(self.player.current_index, 0)

        if self._fade_window is None:
            from gui.widgets.fade_window import QDMFadeWindow

            self._fade_window = QDMFadeWindow()
            self._fade_window.on_applied = self.refresh

        self._fade_window.setTarget(self.player, index)
        self._fade_window.show()
        self._fade_window.raise_()

    def closeFadeWindow(self):
        """Drop the editor along with the session it was editing."""
        if self._fade_window is not None:
            self._fade_window.close()
            self._fade_window = None

    def onTogglePlay(self):
        if self.player is None:
            return
        if self.player.is_playing:
            self.player.pause()
        elif not self._bannerBlocking():
            self.player.play()
        self.refresh()
