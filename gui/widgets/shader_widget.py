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
        self._vsync = True
        self._ctx = None

        # Internal states
        if self.fullscreen:
            self.resizable = False

        # Specify OpenGL context parameters
        self.initFormat()

        # Create the OpenGL widget
        super().__init__(self.fmt)
        self.title = self._title

        self.tic = 0
        self.initUI()

        # Attach to the context
        self.init_mgl_context()
        self.set_default_viewport()

        # Audio features parameters
        self.last_kick_count = self.last_hat_count = self.last_snare_count = 0

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
        center_window_position = (
            int(self.geometry().x() - self.width / 2),
            int(self.geometry().y() - self.height / 2),
        )
        self.move(*center_window_position)
        self._buffer_width = self._width
        self._buffer_height = self._height

        # Needs to be set before show()
        self.resizeGL = self.resize

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
        self._ctx = moderngl.create_context(self.gl_version[0] * 100 + self.gl_version[1])
        self.screen = self._ctx.detect_framebuffer()
        self.init_fbo_manager()

    def init_fbo_manager(self):
        self.fbo_manager = FBOManager(self.ctx)

    def paintGL(self):
        self.makeCurrent()
        self._ctx.clear(color=(0.0, 0.0, 0.0))
        self.app.render(self.app._last_audio_features)

    def resize(self, width: int, height: int) -> None: # type: ignore[override] # FIXME?
        self._width = width * self.devicePixelRatio()
        self._height = height * self.devicePixelRatio()
        self.width = self._width # type: ignore[assignment] # FIXME?
        self.height = self._height # type: ignore[assignment] # FIXME?
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
