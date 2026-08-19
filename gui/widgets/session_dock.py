"""Live session dock: state list, transport, and the validation banner."""

from PyQt5.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
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
        self.chk_loop = QCheckBox("Loop")
        self.chk_loop.setToolTip(
            "Advancing past the last state returns to the first one"
        )
        self.chk_loop.setEnabled(False)
        transport.addWidget(self.chk_loop)
        layout.addLayout(transport)

        timer_row = QHBoxLayout()
        timer_row.addWidget(QLabel("Timer:"))
        self.spin_timer = QDoubleSpinBox()
        self.spin_timer.setRange(0.0, 3600.0)
        self.spin_timer.setDecimals(1)
        self.spin_timer.setSingleStep(0.5)
        self.spin_timer.setSuffix(" s")
        # 0 is how a timer is taken off again, so it reads as what it does.
        self.spin_timer.setSpecialValueText("manual")
        self.spin_timer.setToolTip(
            "How long the selected state holds before advancing (0 = manual)"
        )
        self.spin_timer.setEnabled(False)
        timer_row.addWidget(self.spin_timer)
        self.btn_apply_timer = QPushButton("Apply to all")
        self.btn_apply_timer.setEnabled(False)
        timer_row.addWidget(self.btn_apply_timer)
        timer_row.addStretch()
        layout.addLayout(timer_row)

        self.setLayout(layout)

        self.btn_prev.clicked.connect(self.onPrev)
        self.btn_next.clicked.connect(self.onNext)
        self.btn_play.clicked.connect(self.onTogglePlay)
        self.btn_run_anyway.clicked.connect(self.onRunAnyway)
        self.btn_reload.clicked.connect(self.onFixAndReload)
        self.btn_capture.clicked.connect(self.onCapture)
        self.btn_fade.clicked.connect(self.onFade)
        self.chk_loop.toggled.connect(self.onLoopToggled)
        self.spin_timer.valueChanged.connect(self.onTimerChanged)
        self.btn_apply_timer.clicked.connect(self.onApplyTimerToAll)
        self.state_list.currentRowChanged.connect(self.onSelectionChanged)

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
        # Rebuilding the list drops the selection, and editing a timer
        # refreshes to redraw that state's label -- without restoring it,
        # the next edit would land on a different state than the one the
        # user is looking at.
        selected = self.state_list.currentRow()

        self.state_list.clear()
        self._refreshLoopCheckbox()
        if self.player is None or self.player.session is None:
            self._refreshTimerControls()
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

        if 0 <= selected < self.state_list.count():
            self.state_list.setCurrentRow(selected)

        self.btn_play.setText("❚❚ Pause" if self.player.is_playing else "▶ Play")
        self._refreshTimerControls()

    def _refreshLoopCheckbox(self):
        """Display the session's loop flag without writing it back.

        Signals are blocked around setChecked: a refresh is a read of the
        model, so it must not re-enter onLoopToggled, which is a write.
        """
        session = self.player.session if self.player is not None else None
        self.chk_loop.blockSignals(True)
        self.chk_loop.setEnabled(session is not None)
        self.chk_loop.setChecked(session is not None and session.loop)
        self.chk_loop.blockSignals(False)

    def onLoopToggled(self, checked):
        if self.player is None or self.player.session is None:
            return
        self.player.session.loop = checked

    # -- per-state timer ----------------------------------------------------

    def _selectedIndex(self):
        """The state the per-state controls act on, or -1 for none.

        Falls back to the playing state so the controls still mean
        something before anything has been clicked in the list.
        """
        if self.player is None or self.player.session is None:
            return -1
        states = self.player.session.states
        index = self.state_list.currentRow()
        if index < 0:
            index = max(self.player.current_index, 0)
        return index if 0 <= index < len(states) else -1

    @staticmethod
    def _timer_seconds(trigger):
        """The duration a trigger displays as, 0 for anything untimed.

        A hand-edited file can carry a timer with a non-numeric duration;
        validate_session reports it, and here it simply reads as 0 rather
        than raising while the dock is being drawn.
        """
        if not trigger or trigger.get("type") != "time":
            return 0.0
        try:
            return float(trigger["seconds"])
        except (KeyError, TypeError, ValueError):
            return 0.0

    def _refreshTimerControls(self):
        """Display the selected state's timer without writing it back.

        Signals are blocked around setValue for the same reason as the loop
        checkbox: a refresh reads the model, onTimerChanged writes it.
        """
        index = self._selectedIndex()
        trigger = (
            self.player.session.states[index].trigger if index >= 0 else None
        ) or {}
        # Audio triggers are only authorable by hand in the .pnlive today,
        # so the spinbox must not offer to overwrite one.
        is_audio = trigger.get("type") == "audio"
        editable = index >= 0 and not is_audio

        self.spin_timer.blockSignals(True)
        self.spin_timer.setEnabled(editable)
        # The box sits at 0 for every untimed state, and 0 shows as its
        # special text -- which must not claim "manual" on a state that is
        # actually driven by audio.
        self.spin_timer.setSpecialValueText("audio" if is_audio else "manual")
        self.spin_timer.setValue(self._timer_seconds(trigger))
        self.spin_timer.blockSignals(False)
        self.btn_apply_timer.setEnabled(index >= 0)

    @staticmethod
    def _makeTrigger(seconds):
        if seconds <= 0:
            return {"type": "manual"}
        return {"type": "time", "seconds": seconds}

    def onSelectionChanged(self, row):
        self._refreshTimerControls()

    def onTimerChanged(self, seconds):
        index = self._selectedIndex()
        if index < 0:
            return
        state = self.player.session.states[index]
        if (state.trigger or {}).get("type") == "audio":
            return
        state.trigger = self._makeTrigger(seconds)
        self.refresh()

    def onApplyTimerToAll(self):
        """Time every state at once -- the usual way to start a set running.

        Audio-triggered states keep their trigger: they were hand-authored,
        and a blanket timer would quietly throw that work away.
        """
        if self.player is None or self.player.session is None:
            return
        seconds = self.spin_timer.value()
        for state in self.player.session.states:
            if (state.trigger or {}).get("type") == "audio":
                continue
            # A fresh dict per state: sharing one would make a later edit
            # of any single state silently retime all of them.
            state.trigger = self._makeTrigger(seconds)
        self.refresh()

    @staticmethod
    def _fade_summary(state):
        """Which states ease in, visible at a glance during a set."""
        fade = getattr(state, "fade", None)
        if fade is None or not fade.params:
            return ""
        return "  ~%gs ×%d" % (fade.duration, len(fade.params))

    @staticmethod
    def _trigger_summary(trigger):
        if trigger and trigger.get("type") == "time":
            seconds = QDMSessionDock._timer_seconds(trigger)
            return "timer %gs" % seconds if seconds > 0 else "timer ?"
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
