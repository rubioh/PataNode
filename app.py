from PyQt5.QtOpenGL import *
from node.patanode import PataNode
from glcontext import GLWindow

class PataShade(PataNode):

    def __init__(self):
        super().__init__()
        self.initGLWindow()

    
    def initGLWindow(self):
        self.glwindow = GLWindow(self)

    def show(self):
        super().show()
        #self.glwindow.show()

