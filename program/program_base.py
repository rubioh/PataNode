import numpy as np
from program.program_conf import CTXError

class ProgramBase:

    def __init__(
        self,
        ctx=None,
        major_version=3,
        minor_version=3,
        win_size=(960, 540)
    ):
        if ctx is None:
            raise CTXError("No moderngl ctx given to the program class '%s'"%self.__class__.__name__)
        else:
            self.ctx = ctx

        self._title = None

        self.major_version = major_version
        self.minor_version = minor_version

        self.win_size = win_size
        self._output_fbo = None
        self.vao = None
    
        # Fbos specification 
        self.fbos_win_size, self.fbos_components, self.fbos_dtypes = [], [], []
        self._required_fbos = 1
        self.fbos = None

        self.vert_path = None
        self.frag_path = None

    def initProgram(self, init_vbo=True):
        raise NotImplementedError
    
    def reloadProgram(self):
        self.initProgram(init_vbo=False)

    @property
    def required_fbos(self):
        return self._required_fbos

    @required_fbos.setter
    def required_fbos(self, value):
        self._required_fbos = value

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    @property
    def win_size(self):
        return self._win_size

    @win_size.setter
    def win_size(self, value):
        self._width = value[0]
        self._height = value[1]
        self._win_size = (self._width, self._height)

    def getFBOSpecifications(self):
        return (self.fbos_win_size, self.fbos_components, self.fbos_dtypes)

    def connectFbos(self, fbos=None):
        assert len(fbos) == self.required_fbos
        self.fbos = fbos
        return True

    def bindUniform(self, af):
        try:
            self.program['iResolution'] = self.win_size
        except:
            pass

    def render(self):
        raise NotImplementedError
