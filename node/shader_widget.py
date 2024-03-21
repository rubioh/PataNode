from PyQt5 import QtOpenGL, QtCore, QtWidgets, QtGui
from program.program_manager import FBOManager
import moderngl
import numpy as np
import time

import PyQt5


class ShaderWidget(QtOpenGL.QGLWidget):
    def __init__(self, app, title='GL Widget', gl_version=(3,3), size=(1280, 720), resizable=True, fullscreen=False):
        self.app = app
        self._title = title
        self.gl_version = gl_version
        self.width, self.height = int(size[0]), int(size[1])
        self.resizable = resizable
        self.fullscreen = fullscreen
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
        
        self.initUI()

        # Attach to the context
        self.init_mgl_context()
        self.initQTimer()
        self.set_default_viewport()


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
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding,
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

    def initFormat(self):
        self.fmt = QtOpenGL.QGLFormat()
        self.fmt.setVersion(self.gl_version[0], self.gl_version[1])
        self.fmt.setProfile(QtOpenGL.QGLFormat.CoreProfile)
        self.fmt.setDepthBufferSize(24)
        self.fmt.setStencilBufferSize(8)
        self.fmt.setDoubleBuffer(True)
        self.fmt.setSwapInterval(1 if self._vsync else 0)

    def initQTimer(self):
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(int(1/60*1000))

    def set_default_viewport(self):
        self._viewport = (0, 0, self._buffer_width, self._buffer_height)
        self._ctx.screen.viewport = self._viewport


    def init_mgl_context(self):
        self._ctx = moderngl.create_context(
            self.gl_version[0] * 100 + self.gl_version[1])
        self.screen = self._ctx.detect_framebuffer()
        self.init_fbo_manager()

    def init_fbo_manager(self):
        self.fbo_manager = FBOManager(self.ctx)

    def paintGL(self):
        self.makeCurrent()
        self._ctx.clear(color=(.0,np.cos(time.time())*.5+.5,.0))
        print(self._ctx.screen.width, self._ctx.screen.height)
        self.app.render()

    def resize(self, width: int, height: int) -> None:
        self._width = width * self.devicePixelRatio()
        self._height = height * self.devicePixelRatio()
        self._buffer_width = width
        self._buffer_height = height
        if self._ctx is not None:
            self.set_default_viewport()

    def close_event(self, event) -> None:
        """The standard PyQt close events

        Args:
            event: The qtevent instance
        """
        #TODO ca en propre
        self.hide()
        #self.close()

    def close(self):
        """Close the window"""
        self.timer.stop()
        super().close()

