import copy
import numpy as np
from program.program_conf import CTXError, SQUARE_VERT_PATH, UnuseUniformError, GLSLImplementationError, get_square_vertex_data
from nodeeditor.utils import dumpException


DEBUG = False

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
        self.programs_uniforms = ProgramsUniforms(self)

        self.previous_programs = {}
        self.previous_vaos = {}

    ########################
    # Protected parameters #
    ########################
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
    ###########################################


    ###############################
    # Loading and Programs Things #
    ###############################
    def initProgram(self, reload=False):
        """
            Initialize all the programs for the rendering
            each program and relativ vao are instanciate with loadProgramToCtx with name :
                {name}program and {name}vao
        """
        raise NotImplementedError

    def loadProgramToCtx(self, vert_path, frag_path, reload=False, name=""):
        """
            Create a program named {name}program
                   a vao     named {name}vao     
                   a uniforms dictionnary corresponding to the program
            On reloading : 
                Do some stuff to register the previous working state of the program
                in order to reinstanciate it if the new version failed to compile/execute
        """
        vert = open(vert_path, 'r').read()
        frag = open(frag_path, 'r').read()
        if not reload:
            if vert_path != SQUARE_VERT_PATH:
                self.vertex_shader_glsl_paths.append(vert_path)
            self.fragment_shader_glsl_paths.append(frag_path)
            # Instanciate the vertex buffer object {name}vbo
            setattr(self, name+'vbo', self.ctx.buffer(get_square_vertex_data()))
        program = self.ctx.program(vertex_shader=vert, fragment_shader=frag)
        vao = self.ctx.vertex_array(program, [(getattr(self, name+'vbo'), "2f", "in_position")])
        if reload:
            # Save a copy of the previous program on reload
            self.storePreviousProgramVersion(program, vao, name)
            # TODO self.storePreviousUniformsBinding()
        else:
            setattr(self, name+'program', program)
            setattr(self, name+'vao', vao)
        self.initUniformsForProgram(frag, name)

    def storePreviousProgramVersion(self, program, vao, name):
        # Program
        setattr(self, name+"program_old", getattr(self, name+"program"))
        setattr(self, name+"program", program)
        self.previous_programs[name] = getattr(self, name+"program_old")
        # VAO
        setattr(self, name+"vao_old", getattr(self, name+"vao"))
        setattr(self, name+"vao", vao)
        self.previous_vaos[name] = getattr(self, name+"vao_old")
        if DEBUG: print("New program version is ", getattr(self, name+"program"), 
                        "\nOld program version is ", getattr(self, name+"program_old"))

    def releasePreviousProgramVersion(self):
        for key, program in self.previous_programs.items():
            program.release()
        for key, vao in self.previous_vaos.items():
            vao.release()
        # inutile mais au cas où...
        self.previous_programs = {}
        self.previous_vaos = {}

    def reloadPreviousProgramVersion(self):
        for name, program in self.previous_programs.items():
            if DEBUG: print('Program %s'%name, "with reference", getattr(self, name+"program"), " is reloaded with ", program)
            setattr(self, name+"program", program)
        for name, vao in self.previous_vaos.items():
            if DEBUG: print('Vao %s'%name, "with reference", getattr(self, name+"vao"), " is reloaded with ", vao)
            setattr(self, name+"program", program)
            setattr(self, name+"vao", vao)
        self.bindUniform(None)

    def reloadProgram(self):
        self.releasePreviousProgramVersion()
        self.initProgram(reload=True)

    def reloadProgramSafely(self):
        if DEBUG: print("Program %s: start reloading safely"%self.__class__.__name__)
        if DEBUG: print(self.vbo, self.vao, self.program)
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
        if DEBUG: print(self.vbo, self.vao, self.program)
        if DEBUG: print("Program %s: success while reloading program"%self.__class__.__name__)

    def getGLSLCodePath(self):
        return self.vertex_shader_glsl_paths + self.fragment_shader_glsl_paths
    ############################

    ##############
    # FBO Things #
    ##############
    def getFBOSpecifications(self):
        return (self.fbos_win_size, self.fbos_components, self.fbos_dtypes)

    def connectFbos(self, fbos=None):
        assert len(fbos) == self.required_fbos
        self.fbos = fbos
        return True
    ##########################

    #####################
    # Parameters Things #
    #####################
    def initAdaptableParameters(self, 
                    name="no_name", 
                    value=0, 
                    minimum=0, 
                    maximum=1, 
                    type="f4",
                    widget_type="Slider"):
        setattr(self, name, value)
        self.adaptable_parameters_dict[name] = {
            "name": name,
            "minimum": minimum,
            "maximum": maximum,
            "type":  type,
            "value": value,
            "connect": lambda v: self.setAdaptableParameters(name, v),
            "widget": widget_type
        }
    
    def getAdaptableParameters(self):
        # Update parameters value in the dictionnary (only here)
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
    #####################


    ###################
    # Uniforms Things #
    ###################
    def initUniformsForProgram(self, _file, program_name):
        self.programs_uniforms.addProgram(_file, program_name)

    def initUniformsBinding(self, binding, program_name):
        self.programs_uniforms.initBinding(program_name, binding)

    def getUniformsBinding(self):
        return self.programs_uniforms.getUniformsBinding()

    def bindUniform(self, af):
        try:
            self.program['iResolution'] = self.win_size
        except:
            pass
    #########################

    def render(self):
        raise NotImplementedError


class UniformsLookup():
    def __init__(self, uniforms, callback, protected):
        self.protected = protected
        self.uniforms = self.protect(uniforms)
        self.callback = callback
    def protect(self, uniforms):
        uniforms_copy = copy.deepcopy(uniforms)
        for program in uniforms_copy.keys():
            for to_protect in self.protected:
                if to_protect in uniforms_copy[program].keys():
                    del uniforms_copy[program][to_protect]
        return uniforms_copy
    def __getitem__(self, key):
        return self.uniforms[key]
    def __len__(self):
        return len(self.uniforms)
    def __iter__(self):
        return iter(self.uniforms)

class ProgramsUniforms():

    def __init__(self, parent=None):
        self.parent = parent
        self.init_binding = {}
        self.uniforms = {}
        self.programs = {}
        self.lookup = None
        self.protected = ['iResolution']

    def addProgram(self, file, program_name):
        self.uniforms[program_name] = {}
        self.programs[program_name] = getattr(self.parent, program_name+"program")
        file_lines = file.split(';')
        for line in file_lines:
            if "uniform" in line:
                tmp = line.split(" ")
                uniform_name = tmp[2]
                type = None
                self.addUniform(program_name, uniform_name, type)

    def addUniform(self, program_name, uniform_name, type_name):
        self.uniforms[program_name][uniform_name] = {
            "type": type_name,
            "param_name": None
        }

    def getUniformsBinding(self):
        if self.lookup is None:
            self.lookup = UniformsLookup(self.uniforms, self.changeBinding, self.protected)
        return self.lookup

    def initBinding(self, program_name, binding):
        uniforms = self.uniforms[program_name]
        for uniform_name, param_name in binding.items():
            uniforms[uniform_name]["type"] = None
            uniforms[uniform_name]["param_name"] = param_name
        self.init_binding[program_name] = copy.deepcopy(uniforms)

    def changeBinding(self, program_name, uniform_name, param_name, type):
        if param_name == 'default':
            uniforms = self.uniforms[program_name]
            uniforms[uniform_name]["type"] = None
            uniforms[uniform_name]["param_name"] = self.init_binding[program_name][uniform_name]['param_name']
        else:
            uniforms = self.uniforms[program_name]
            uniforms[uniform_name]["type"] = type if type == 'audio_features' else None
            uniforms[uniform_name]["param_name"] = param_name


    def bindUniformToProgram(self, audio_features, program_name=''):
        program = self.programs[program_name]
        for uniform_name, info  in self.uniforms[program_name].items():
            if info["param_name"] is not None: # ie if this uniform is set to a params
                if info["type"] == 'audio_features':
                    program[uniform_name] = audio_features[info["param_name"]]
                else:
                    program[uniform_name] = getattr(
                            self.parent, 
                            info["param_name"]
                    )

    
    #def changeParamBinding(self, program_name, uniform_name, param_name):
    #    self.uniforms[program][uniform_name] = param_name

    #def getParamName(self, program_name, uniform_name, param_name):
    #    return self.uniforms[program_name][uniform_name][param_name]
