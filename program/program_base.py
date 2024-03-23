import numpy as np
from program.program_conf import CTXError, SQUARE_VERT_PATH, UnuseUniformError, GLSLImplementationError
from nodeeditor.utils import dumpException


DEBUG = True

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

        self.vertex_shader_glsl_paths = []
        self.fragment_shader_glsl_paths = []

        self.adaptable_parameters_dict = {}

    def initProgram(self, reload=False):
        raise NotImplementedError

    def loadProgramToCtx(self, vert_path, frag_path, reload=False):
        vert = open(vert_path, 'r').read()
        frag = open(frag_path, 'r').read()
        if not reload:
            if vert_path != SQUARE_VERT_PATH:
                self.vertex_shader_glsl_paths.append(vert_path)
            self.fragment_shader_glsl_paths.append(frag_path)
        return self.ctx.program(vertex_shader=vert, fragment_shader=frag)

    def reloadProgram(self):
        self.initProgram(reload=True)

    def reloadProgramSafely(self):
        if DEBUG: print("Program %s: start reloading safely"%self.__class__.__name__)
        # Try to reload the program
        try:
            self.reloadProgram()
        except:
            raise GLSLImplementationError

        # Try to bind uniforms to the program
        try:
            self.bindUniform(None) # TODO remove None here 
        except:
            raise UnuseUniformError
        if DEBUG: print("Program %s: success while reloading program"%self.__class__.__name__)


    def getGLSLCodePath(self):
        return self.vertex_shader_glsl_paths + self.fragment_shader_glsl_paths

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

    def initAdaptableParameters(self, 
                    name="no_name", 
                    value=0, 
                    minimum=0, 
                    maximum=1, 
                    type="f4",
                    widget_type=0):
        setattr(self, name, value)
        self.adaptable_parameters_dict[name] = {
            "name": name,
            "minimum": minimum,
            "maximum": maximum,
            "type":  type,
            "value": value,
            "connect": lambda v: self.setAdaptableParameters(name, v),
            "widget": 0
        }
    
    def getAdaptableParameters(self):
        for params in self.adaptable_parameters_dict.keys():
            self.adaptable_parameters_dict[params]["value"] = getattr(self, params)
        return self.adaptable_parameters_dict

    def setAdaptableParameters(self, params, value):
        """
            params : Parameters name (str)
            value : float or anything...
        """
        if not hasattr(self, params):
            print("Params %s"%params, " is not a parameter of program %s"%self.__class__.__name__)
        else:
            setattr(self, params, value)
            if DEBUG: print("Params %s set to value"%params, str(value))


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
