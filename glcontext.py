from PyQt5.QtOpenGL import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import moderngl



class GLWindow(QGLWidget):

    def __init__(self, parent=None):
        self.gl_version = (3, 3)
        self.resizable = True
        gl = QGLFormat()
        gl.setVersion(*self.gl_version)
        gl.setProfile(QGLFormat.CoreProfile)
        gl.setDepthBufferSize(24)
        gl.setStencilBufferSize(8)
        gl.setDoubleBuffer(True)
        gl.setSwapInterval(1)
        super().__init__(gl)
        
        self.setParent(parent)
        
        # TODO WIDTH
        self._width = 960
        self._height = 540
        self._ctx = None

        self.initUI()

    def initUI(self):
        size_policy = QSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Expanding
        )
        self.setSizePolicy(size_policy)
        self.resize(self._width, self._height)

        center_window_position = (
                self.geometry().x() - self._width//2,
                self.geometry().y() - self._height//2,
        )
        self.move(*center_window_position)
        self.resizeGL = True
        self.setCursor(
            Qt.ArrowCursor
        )

    def initializeGL(self):
        ...

    def initContext(self):
        self._ctx = moderngl.create_context(
            self.gl_version[0] * 100 + self.gl_version[1]
        )

        self.screen = self._ctx.detect_framebuffer()

        self._buffer_width = self._width * self.devicePixelRatio()
        self._buffer_height = self._height* self.devicePixelRatio()

        self.set_default_viewport()

    def paintGL(self):
        try:
            if self._ctx is None:
                self.initContext()
            self.makeCurrent()
            self.screen.use()
            self._ctx.clear(color=(.1,.1,.1))
        except Exception as e: print(e)

    def resizeGL(self, width, height):
        ...

    def set_default_viewport(self):
        self._viewport = (0, 0, self._buffer_width, self._buffer_height)
        self._ctx.screen.viewport = self._viewport
