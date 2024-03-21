from PyQt5.QtOpenGL import *
from node.patanode import PataNode
from program.program_manager import ProgramManager, FBOManager

class PataShade(PataNode):

    def __init__(self):
        super().__init__()
        self.fbo_manager = FBOManager(self.ctx)



