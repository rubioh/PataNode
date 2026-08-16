import time

import moderngl
from PyQt5 import QtCore, QtOpenGL, QtWidgets

import profiler
from program.program_manager import FBOManager


class ShaderWidget(QtOpenGL.QGLWidget):
    def __init__(
        self,
        app,
        title="GL Widget",
        gl_version=(3, 3),
        size=(1280, 720),
        resizable=True,
        fullscreen=False,
    ):
        self.app = app
        self.app.setShaderWidget(self)
        self._title = title
        self.gl_version = gl_version
        self.width, self.height = int(size[0]), int(size[1])
        self.resizable = resizable
        self.fullscreen = fullscreen
        self._fixed_aspect_ratio = 16 / 9
        # --vsync decides, so an A/B needs no edit and each profile report is
        # stamped with which way it ran. On is the shipping behaviour.
        self._vsync = getattr(getattr(app, "args", None), "vsync", "on") != "off"
        self._ctx = None

        # Internal states
        if self.fullscreen:
            self.resizable = False

        # Specify OpenGL context parameters
        self.initFormat()

        # Create the OpenGL widget
        super().__init__(self.fmt)
        self.title = self._title

        # Before initUI: it calls show(), which can dispatch a paint, and
        # paintGL consults the loop mode.
        self.initRenderLoop()

        self.tic = 0
        self.initUI()

        # Attach to the context
        self.init_mgl_context()
        self.set_default_viewport()

        # Audio features parameters
        self.last_kick_count = self.last_hat_count = self.last_snare_count = 0

    def initRenderLoop(self):
        """Choose how the next frame gets requested. See --paint-loop.

        Two ways to keep a render loop turning under Qt, and they differ in
        which Windows message carries the request:

        "event"  -- update(), the way this has always worked. On a QGLWidget
                    (WA_PaintOnScreen) that becomes a native WM_PAINT, which
                    Windows delivers only once the message queue is otherwise
                    empty. WM_PAINT is the lowest-priority message there is.

        "timer"  -- a zero-delay QTimer, which is an ordinary posted event and
                    is not subject to that rule.

        Measured before this existed: the paint request waited 5-7 ms while
        timer messages arrived on schedule, and the wait grew with GPU load
        while the GUI thread sat idle. This switch exists to find out whether
        the message type is the reason.
        """
        args = getattr(self.app, "args", None)
        self._loop_mode = getattr(args, "paint_loop", "timer")

        # 0 is a Qt zero-timer, which is not an OS timer at all: the dispatcher
        # posts itself a ZeroTimerEvent and consequently never blocks waiting
        # for messages, spinning through every pending event between frames.
        # --profile-events showed that event (type 154) arriving once per frame
        # and carrying 451 ms/s. A non-zero interval gives a real timer and
        # lets the loop idle; --frame-interval exists to compare the two.
        self._frame_interval = max(0, int(getattr(args, "frame_interval", 0) or 0))

        # Target cadence. Without it the loop redraws as fast as the driver
        # allows, which on a 144 Hz panel with vsync means 72 fps -- fast, but
        # not a rate anyone chose. Deadline-based rather than "sleep N ms
        # after each frame": the latter gives a period of N + however long the
        # frame took, so a 16 ms sleep on a 13 ms frame produces 34 fps, not
        # 60. See _scheduleNextFrame.
        fps = float(getattr(args, "fps", 0.0) or 0.0)
        self._frame_period_ns = int(1e9 / fps) if fps > 0 else 0
        self._next_deadline_ns = 0

        # One reusable single-shot timer rather than QTimer.singleShot, which
        # would allocate a timer object per frame.
        self._frame_timer = QtCore.QTimer(self)
        self._frame_timer.setSingleShot(True)
        self._frame_timer.setTimerType(QtCore.Qt.PreciseTimer)
        self._frame_timer.timeout.connect(self.renderFrame)

    @property
    def size(self):
        return self._width, self._height

    @size.setter
    def size(self, value):
        pos = self.position
        self._widget.setGeometry(pos[0], pos[1], value[0], value[1])

    @property
    def ctx(self):
        return self._ctx

    def initUI(self):
        size_policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.setSizePolicy(size_policy)
        self.resize(self.width, self.height)

        # Center the window on the screen if in window mode
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        center_window_position = (
            screen.x() + (screen.width() - self.width) // 2,
            screen.y() + (screen.height() - self.height) // 2,
        )
        self.move(*center_window_position)
        self._buffer_width = self._width
        self._buffer_height = self._height

        # Needs to be set before show()
        self.resizeGL = self.resize

        # Qt would otherwise swap for us, right after paintGL returns and
        # outside anything we can time. Swapping explicitly at the end of
        # paintGL is the documented way to take that over, and it is the only
        # stretch of the render loop that is still unmeasured.
        self.setAutoBufferSwap(False)

        self.show()

        # We want mouse position events
        self.setMouseTracking(True)

        # Disable cursor
        self.setCursor(QtCore.Qt.BlankCursor)

    def initFormat(self):
        self.fmt = QtOpenGL.QGLFormat()
        self.fmt.setVersion(self.gl_version[0], self.gl_version[1])
        self.fmt.setProfile(QtOpenGL.QGLFormat.CoreProfile)
        self.fmt.setDepthBufferSize(24)
        self.fmt.setStencilBufferSize(8)
        self.fmt.setDoubleBuffer(True)
        self.fmt.setSwapInterval(1 if self._vsync else 0)

    def init_mgl_context(self):
        self._ctx = moderngl.create_context(
            self.gl_version[0] * 100 + self.gl_version[1]
        )
        self.screen = self._ctx.detect_framebuffer()
        self.init_fbo_manager()
        self.init_profiler()

    def init_profiler(self):
        """Wire up --profile, if it was asked for.

        Here rather than in app.py because the profiler needs the GL context,
        and this is the first point at which one exists. The app already holds
        the parsed args by now (PataShadeApp assigns self.args before
        super().__init__() builds this widget), but a ShaderWidget constructed
        from a test has no args at all -- hence the getattr chain.
        """
        args = getattr(self.app, "args", None)
        every = getattr(args, "profile", 0)

        if not every:
            self._profiler = None
            return

        # A None ctx disables the GL timer queries: the profiler already skips
        # them when it has no context, so --profile-no-gpu needs no separate
        # switch. Everything CPU-side stays measured.
        ctx = None if getattr(args, "profile_no_gpu", False) else self._ctx

        # Every setting that changes how the loop is paced, stamped on each
        # report. Two runs differing only by a flag are otherwise impossible to
        # tell apart once the output is copied out of the terminal.
        target = (
            "%.0f" % (1e9 / self._frame_period_ns) if self._frame_period_ns else "libre"
        )
        context = "cible=%s fps  vsync=%s  paint-loop=%s  %dx%d  gpu-q=%s" % (
            target,
            "on" if self._vsync else "off",
            self._loop_mode,
            self._buffer_width,
            self._buffer_height,
            "off" if ctx is None else "on",
        )
        self._profiler = profiler.enable(ctx, report_every=every, context=context)

    def init_fbo_manager(self):
        self.fbo_manager = FBOManager(self.ctx)

    def renderFrame(self):
        """One turn of the render loop, driven by _frame_timer.

        Deliberately not reached through paintEvent: that is the whole point of
        --paint-loop timer. Drawing to a QGLWidget outside its paint event is
        legitimate as long as the context is current, which makeCurrent below
        guarantees.
        """
        if not self.isVisible():
            # Nothing to draw into, and re-arming would spin for nothing. The
            # watchdog in app.start_jobs restarts the loop when the window
            # comes back.
            return

        self.drawFrame()

        profiler.PROFILER.mark_dispatch()
        self._scheduleNextFrame()

    def _scheduleNextFrame(self):
        """Arm the timer so frames land on a fixed cadence.

        The deadline advances by exactly one period per frame regardless of
        how long this one took, so the long-run rate is exact even though Qt
        timers only take whole milliseconds -- a 16.67 ms period alternates
        between 16 and 17 ms sleeps and averages out correctly.
        """
        if not self._frame_period_ns:
            self._frame_timer.start(self._frame_interval)
            return

        now = time.perf_counter_ns()

        if self._next_deadline_ns == 0:
            self._next_deadline_ns = now

        self._next_deadline_ns += self._frame_period_ns

        if self._next_deadline_ns <= now:
            # Overran the budget. Skip whole slots to the next one still in
            # the future, rather than restarting the cadence from here: that
            # keeps the rate an exact fraction of the target (60 falls to 30,
            # then 20) instead of drifting to a ragged in-between value, which
            # reads as far worse motion. Never fires a backlog back to back.
            missed = (now - self._next_deadline_ns) // self._frame_period_ns + 1
            self._next_deadline_ns += missed * self._frame_period_ns

        delay_ms = int(round((self._next_deadline_ns - now) / 1e6))
        self._frame_timer.start(max(0, delay_ms))

    def ensureRenderLoopRunning(self):
        """Restart the loop if no frame is pending. Called by the watchdog.

        Idempotent by construction -- an already-armed timer is left alone --
        so the watchdog can fire as often as it likes without doubling the
        frame rate or stacking requests.
        """
        if self._loop_mode == "event":
            profiler.PROFILER.mark_dispatch()
            self.update()
        elif not self._frame_timer.isActive():
            # Restarting after a gap (window hidden, frame lost): drop the old
            # deadline so the cadence begins again from now.
            self._next_deadline_ns = 0
            self._scheduleNextFrame()

    def paintGL(self):
        # In "timer" mode this is only ever an OS-initiated paint -- a resize
        # or a re-exposure -- and there is nothing to do: renderFrame is
        # already redrawing continuously, so the window is at most one frame
        # stale. Drawing here as well produced a second full render back to
        # back with the loop's own, which showed up as near-zero frame
        # periods: wasted GPU work, and a frame counter reading high because
        # it counted renders rather than presented frames.
        if self._loop_mode != "event":
            return

        self.drawFrame()
        profiler.PROFILER.mark_dispatch()
        self.update()

    def drawFrame(self):
        """Draw and present one frame. Does not request the next one."""
        # Timed separately, and deliberately outside the frame span. These are
        # the first GL calls after the event loop hands control back, which is
        # where an OpenGL driver blocks the CPU when the GPU is behind: the
        # stall is charged to whatever call happens to find the command queue
        # full, not to the draw that caused it.
        with profiler.PROFILER.gui_span("makeCurrent"):
            self.makeCurrent()

        with profiler.PROFILER.gui_span("clear"):
            self._ctx.clear(color=(0.0, 0.0, 0.0))

        # This widget is built from PataNode.__init__, so paints can be
        # dispatched before the app has the state render() needs
        # (_last_audio_features, mapping, current_node_editor_widget). PyQt
        # aborts the process on an exception raised inside a virtual, so an
        # unguarded paint here is a hard startup crash rather than a warning.
        if getattr(self.app, "render_ready", False):
            prof = getattr(self, "_profiler", None)

            if prof is None:
                self.app.render(self.app._last_audio_features)
            else:
                # try/finally, not a bare pair: a node that raises mid-frame
                # would otherwise leave the frame open, and every later frame
                # would accumulate into it.
                prof.begin_frame()
                try:
                    self.app.render(self.app._last_audio_features)
                finally:
                    prof.end_frame()

        # Ours to call because initUI turned off autoBufferSwap. Outside the
        # frame span deliberately: this is not render work, it is the wait for
        # the driver and the compositor to accept the finished frame, and the
        # whole point is to see it as its own line in the report. Runs on every
        # path, including the not-ready one -- skipping it would leave the
        # window showing nothing.
        with profiler.PROFILER.gui_span("swapBuffers"):
            self.swapBuffers()

    def resize(self, width: int, height: int) -> None:  # type: ignore[override] # FIXME?
        self._width = width * self.devicePixelRatio()
        self._height = height * self.devicePixelRatio()
        self.width = self._width  # type: ignore[assignment] # FIXME?
        self.height = self._height  # type: ignore[assignment] # FIXME?
        self._buffer_width = width
        self._buffer_height = height

        if self._ctx is not None:
            self.set_default_viewport()

    def set_default_viewport(self) -> None:
        """
        Calculates and sets the viewport based on window configuration.

        The viewport is based on the configured fixed aspect ratio if set.
        If no fixed aspect ratio is set, the viewport is scaled to the entire
        window size regardless of size.

        Will add black borders and center the viewport if the window does not
        match the configured viewport (fixed only)
        """
        if self._fixed_aspect_ratio:
            expected_width = int(self._buffer_height * self._fixed_aspect_ratio)
            expected_height = int(expected_width / self._fixed_aspect_ratio)

            if expected_width > self._buffer_width:
                expected_width = self._buffer_width
                expected_height = int(expected_width / self._fixed_aspect_ratio)

            blank_space_x = self._buffer_width - expected_width
            blank_space_y = self._buffer_height - expected_height

            blank_space_x = 0
            blank_space_y = 0

            self._viewport = (
                blank_space_x // 2,
                blank_space_y // 2,
                expected_width,
                expected_height,
            )
        else:
            self._viewport = (0, 0, self._buffer_width, self._buffer_height)

        self.ctx.screen.viewport = self._viewport

    def closeEvent(self, event):
        print("ShaderWidget::closeEvent Hide window")
        self.hide()
        event.ignore()

    def close(self):
        """Close the window"""
        self.hide()
