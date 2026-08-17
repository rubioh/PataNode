import time

import moderngl
from PyQt5 import QtCore, QtOpenGL, QtWidgets

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
        # --vsync decides, so an A/B needs no code edit. On is the shipping
        # behaviour. The getattr chain is for tests, which build a
        # ShaderWidget from an app object that has no parsed args.
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
        # paintGL is defined in terms of the loop set up here.
        self.initRenderLoop()

        self.tic = 0
        self.initUI()

        # Attach to the context
        self.init_mgl_context()
        self.set_default_viewport()

        # Audio features parameters
        self.last_kick_count = self.last_hat_count = self.last_snare_count = 0

    def initRenderLoop(self):
        """Set up the self-driving render loop. Nothing is started here.

        The loop asks for its own next frame: renderFrame draws, then arms
        _frame_timer again, so exactly one frame is ever in flight. It
        deliberately does not go through update()/paintEvent. On a QGLWidget
        (WA_PaintOnScreen) a repaint request becomes a native paint message,
        which the window system delivers only once its queue is otherwise
        empty -- and with three timers feeding that queue the request waited
        5-7 ms while the timer messages themselves arrived on schedule. A
        plain timer event is not subject to that.

        The loop is started, and restarted, by ensureRenderLoopRunning.
        """
        args = getattr(self.app, "args", None)

        # Target cadence. Deadline-based rather than "sleep N ms after each
        # frame": the latter gives a period of N plus however long the frame
        # took, so a 16 ms sleep on a 13 ms frame produces 34 fps, not 60.
        # See _scheduleNextFrame.
        fps = float(getattr(args, "fps", 0.0) or 0.0)
        self._frame_period_ns = int(1e9 / fps) if fps > 0 else 0
        self._next_deadline_ns = 0

        # One reusable single-shot timer rather than QTimer.singleShot, which
        # would allocate a timer object per frame.
        self._frame_timer = QtCore.QTimer(self)
        self._frame_timer.setSingleShot(True)
        self._frame_timer.setTimerType(QtCore.Qt.PreciseTimer)
        self._frame_timer.timeout.connect(self.renderFrame)

    def renderFrame(self):
        """One turn of the render loop. Draws, then asks for the next frame.

        Drawing a QGLWidget outside its paint event is legitimate as long as
        the context is current, which drawFrame's makeCurrent guarantees.
        """
        if not self.isVisible():
            # Nothing to draw into, and re-arming would spin for nothing.
            # ensureRenderLoopRunning restarts the loop when the window
            # comes back -- via showShaderWindow, or the app's watchdog.
            return

        self.drawFrame()
        self._scheduleNextFrame()

    def _scheduleNextFrame(self):
        """Arm the timer so frames land on a fixed cadence.

        The deadline advances by exactly one period per frame regardless of
        how long this one took, so the long-run rate is exact even though Qt
        timers only take whole milliseconds: a 16.67 ms period alternates
        between 16 and 17 ms sleeps and averages out correctly.
        """
        if not self._frame_period_ns:
            # Uncapped. Deliberately 1 ms rather than 0: a Qt zero-timer is
            # not an OS timer, it posts itself an event, so the dispatcher
            # never blocks and spins through every pending event between
            # frames. 1 ms is a real timer and still well above any rate the
            # driver will present at.
            self._frame_timer.start(1)
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
        """Start the loop if no frame is pending.

        Idempotent by construction -- an already-armed timer is left alone --
        so the app's watchdog can call it as often as it likes without
        doubling the frame rate or stacking requests.

        This is the only thing that ever starts the loop: initRenderLoop
        creates the timer stopped, and the shader window is hidden at
        startup, so the first frame comes from here.
        """
        if not self._frame_timer.isActive():
            # Restarting after a gap (window hidden, loop paused for
            # teardown): drop the stale deadline so the cadence begins again
            # from now rather than trying to catch up on missed slots.
            self._next_deadline_ns = 0
            self._scheduleNextFrame()

    def stopRenderLoop(self):
        """Stop the loop. Paired with ensureRenderLoopRunning.

        PataNode.closeEvent pauses the jobs before dismantling anything,
        because closeAllSubWindows removes every node in every closing graph
        and a frame landing mid-teardown renders a half-destroyed scene. That
        used to be covered by stopping the shader timer, which was the thing
        driving the frames; now that the loop re-arms itself, stopping the
        timer in app.py is not enough and this has to be stopped too.
        """
        self._frame_timer.stop()

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

        # Qt only swaps automatically as part of handling a paint event, and
        # after this change the frames are drawn from a timer slot instead --
        # so auto-swap would never run for them and nothing would ever be
        # presented. drawFrame calls swapBuffers itself.
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

    def init_fbo_manager(self):
        self.fbo_manager = FBOManager(self.ctx)

    def paintGL(self):
        """Deliberately empty. The render loop draws; this does not.

        Everything reaching here is an OS-initiated paint -- a resize, a
        re-exposure, the window being uncovered. renderFrame is already
        redrawing continuously, so the window is at most one frame stale and
        there is nothing to do.

        Drawing here as well is what the loop used to do, and it produced a
        second full render back to back with the loop's own: wasted GPU work,
        and a frame counter that read high because it was counting renders
        rather than presented frames.
        """

    def drawFrame(self):
        """Draw and present one frame. Does not request the next one."""
        self.makeCurrent()
        self._ctx.clear(color=(0.0, 0.0, 0.0))

        # This widget is built from PataNode.__init__, so frames can be drawn
        # before the app has the state render() needs (_last_audio_features,
        # mapping, current_node_editor_widget).
        if getattr(self.app, "render_ready", False):
            self.app.render(self.app._last_audio_features)

        # Ours to call because initUI turned off autoBufferSwap. Runs on
        # every path, including the not-ready one -- skipping it would leave
        # the window showing nothing at all rather than black.
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
