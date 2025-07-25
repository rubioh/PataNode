import copy

import numpy as np

from program.program_conf import (
    CTXError,
    GLSLImplementationError,
    SQUARE_VERT_PATH,
    UnuseUniformError,
    get_square_vertex_data,
)


DEBUG = False
DEBUG_EVAL = False


class ProgramBase:
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        if ctx is None:
            raise CTXError(
                "No moderngl ctx given to the program class '%s'"
                % self.__class__.__name__
            )
        else:
            self.ctx = ctx

        self._title = None

        self.major_version = major_version
        self.minor_version = minor_version

        self.win_size = win_size
        self._output_fbo = None
        self.vao = None

        # FBOs specification
        self.fbos_win_size = []
        self.fbos_components = []
        self.fbos_dtypes = []
        self.fbos_depth_requirement = []
        self.fbos_num_textures = []
        self._required_fbos = 1
        self.fbos = None

        self.vertex_shader_glsl_paths = []
        self.fragment_shader_glsl_paths = []

        self.adaptable_parameters_dict = {}
        self.cpu_adaptable_parameters_dict = {}
        self.programs_uniforms = ProgramsUniforms(self)

        self.previous_programs = {}
        self.previous_vaos = {}

        # Flags for rendering
        self._already_called = False

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

    @property
    def already_called(self):
        return self._already_called

    @already_called.setter
    def already_called(self, value):
        self._already_called = value

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

    def loadProgramToCtx(
        self,
        vert_path,
        frag_path,
        reload=False,
        name="",
        vao_binding=None,
        varyings=None,
    ):
        """
        Create a program named {name}program
               a vao     named {name}vao
               a uniforms dictionnary corresponding to the program
        On reloading :
            Do some stuff to register the previous working state of the program
            in order to reinstanciate it if the new version failed to compile/execute
        """
        if DEBUG:
            print(
                "ProgramBase::loadProgramToCtx  loading program %s" % name,
                " with vert_path %s and frag_path %s" % (vert_path, frag_path),
                " with varyings %s and vao_binding %s"
                % (str(varyings), str(vao_binding)),
            )

        vert = open(vert_path, "r").read()
        frag = None
        self.name = name

        if frag_path is not None:
            frag = open(frag_path, "r").read()

        if not reload:
            if vert_path != SQUARE_VERT_PATH:
                self.vertex_shader_glsl_paths.append(vert_path)
            else:
                setattr(self, name + "vbo", self.ctx.buffer(get_square_vertex_data()))

            if frag_path is not None:
                self.fragment_shader_glsl_paths.append(frag_path)

        # Instanciate the vertex buffer object {name}vbo
        if varyings is None:
            program = self.ctx.program(vertex_shader=vert, fragment_shader=frag)
        else:
            program = self.ctx.program(
                vertex_shader=vert, fragment_shader=frag, varyings=varyings
            )

        if vao_binding is None:
            vao = self.ctx.vertex_array(
                program, [(getattr(self, name + "vbo"), "2f", "in_position")]
            )
        else:
            vao = self.ctx.vertex_array(program, vao_binding)

        if reload:
            # Save a copy of the previous program on reload
            self.storePreviousProgramVersion(program, vao, name)
            # TODO: self.storePreviousUniformsBinding()
        else:
            setattr(self, name + "program", program)
            setattr(self, name + "vao", vao)

        self.adaptable_parameters_dict[name + "program"] = {}
        self.cpu_adaptable_parameters_dict[name + "program"] = {}

        if frag is None:
            frag = ""

        if vert_path == SQUARE_VERT_PATH:
            vert = "\n"

        self.initUniformsForProgram(frag + vert, name, reload)

        if reload:
            self.reloadUniformsBinding(None, name)

    def storePreviousProgramVersion(self, program, vao, name):
        # Program
        setattr(self, name + "program_old", getattr(self, name + "program"))
        setattr(self, name + "program", program)
        self.previous_programs[name] = getattr(self, name + "program_old")

        # VAO
        setattr(self, name + "vao_old", getattr(self, name + "vao"))
        setattr(self, name + "vao", vao)
        self.previous_vaos[name] = getattr(self, name + "vao_old")

        if DEBUG:
            print(
                "New program version is",
                getattr(self, name + "program"),
                "\nOld program version is",
                getattr(self, name + "program_old"),
            )

    def releasePreviousProgramVersion(self):
        for key, program in self.previous_programs.items():
            program.release()

        for key, vao in self.previous_vaos.items():
            vao.release()

        # Useless, but you never know..
        self.previous_programs = {}
        self.previous_vaos = {}

    def reloadPreviousProgramVersion(self):
        for name, program in self.previous_programs.items():
            if DEBUG:
                print(
                    "Program",
                    name,
                    "with reference",
                    getattr(self, name + "program"),
                    "is reloaded with",
                    program,
                )

            setattr(self, name + "program", program)

        for name, vao in self.previous_vaos.items():
            if DEBUG:
                print(
                    "VAO",
                    name,
                    "with reference",
                    getattr(self, name + "vao"),
                    "is reloaded with",
                    vao,
                )

            setattr(self, name + "program", program)
            setattr(self, name + "vao", vao)

        self.bindUniform(None)

    def reloadProgram(self):
        self.releasePreviousProgramVersion()
        self.initProgram(reload=True)

    def reloadProgramSafely(self):
        if DEBUG:
            print("Program %s: start reloading safely" % self.__class__.__name__)
            print(self.vbo, self.vao, self.program)

        # Try to reload the program
        try:
            self.reloadProgram()
        except Exception:
            raise GLSLImplementationError

        # Try to bind uniforms to the program
        try:
            self.bindUniform(None)  # TODO: remove None here
        except Exception:
            self.reloadPreviousUniformsState()
            raise UnuseUniformError

        if DEBUG:
            print(self.vbo, self.vao, self.program)
            print(
                "Program %s: success while reloading program" % self.__class__.__name__
            )

    def getGLSLCodePath(self):
        return self.vertex_shader_glsl_paths + self.fragment_shader_glsl_paths

    ###########################################

    ##############
    # FBO Things #
    ##############
    def getFBOSpecifications(self):
        dr = None

        if len(self.fbos_depth_requirement):
            dr = self.fbos_depth_requirement

        if len(self.fbos_num_textures) == 0.0:
            self.fbos_num_textures = [1 for i in range(len(self.fbos_win_size))]

        return (
            self.fbos_win_size,
            self.fbos_components,
            self.fbos_dtypes,
            dr,
            self.fbos_num_textures,
        )

    def connectFbos(self, fbos=None):
        assert len(fbos) == self.required_fbos
        self.fbos = fbos
        return True

    ###########################################

    #####################
    # Parameters Things #
    #####################
    def initAdaptableParameters(
        self,
        name="no_name",
        uniform_name="no_name",
        program_name="program",
        value=0,
        minimum=0,
        maximum=1,
        type="f4",
        widget_type="Slider",
    ):
        if uniform_name not in self.adaptable_parameters_dict[program_name].keys():
            self.adaptable_parameters_dict[program_name][uniform_name] = {}

        uniform_parameters = self.adaptable_parameters_dict[program_name][uniform_name]
        uniform_parameters[name] = {
            "name": name,
            #           "minimum": minimum,
            #           "maximum": maximum,
            #           "type":  type,
            "value": value,
            "connect": lambda v: self.setAdaptableParameters(
                program_name, uniform_name, name, v
            ),
            "widget": widget_type,
        }

    def protectAdaptableParameters(self, protected):
        apd = self.adaptable_parameters_dict
        for program_name in apd.keys():
            for uniform_name in apd[program_name].keys():
                gui_uni = apd[program_name][uniform_name]["eval_function"]
                if gui_uni["name"] in protected:
                    gui_uni["protected"] = True
                else:
                    gui_uni["protected"] = False

    def setCpuAdaptableParameters(self, progam_name, name, value):
        self.cpu_adaptable_parameters_dict[progam_name][name]["eval_function"][
            "value"
        ] = value

    #
    #       if self.cpu_adaptable_parameters_dict[progam_name][name]["eval_function"]["callback"]:
    #           self.cpu_adaptable_parameters_dict[progam_name][name]["eval_function"]["callback"](value)

    def add_text_edit_cpu_adaptable_parameter(self, name, value, callback=None):
        uniform_parameters = self.cpu_adaptable_parameters_dict[self.name + "program"]
        uniform_parameters[name] = {
            "eval_function": {
                "name": name,
                "value": value,
                "connect": lambda v: self.setCpuAdaptableParameters(
                    self.name + "program", name, v
                ),
                #               "callback": callback,
                "widget": "TextEdit",
            }
        }

    def initUniformsAdaptableParameters(self, program_name, uniform_name):
        self.initAdaptableParameters(
            name="eval_function",
            uniform_name=uniform_name,
            program_name=program_name,
            value="x",
            minimum=0.25,
            maximum=4.0,
            type="f4",
            widget_type="TextEdit",
        )

    def getAdaptableEvaluationForUniform(self, program_name, uniform_name, x):
        evaluation = self.adaptable_parameters_dict[program_name][uniform_name][
            "eval_function"
        ]["value"]

        try:
            modified_data = eval(evaluation)
            modified_data = float(modified_data)
        except Exception:
            if DEBUG_EVAL:
                print(
                    "eval_function",
                    evaluation,
                    "is not correct.",
                    self.__class__.__name__,
                    "for uniform",
                    uniform_name,
                )
                print("giving raw input in uniforms", uniform_name)

            modified_data = x

        return modified_data

    def getCpuAdaptableParameters(self):
        return self.cpu_adaptable_parameters_dict

    def getGpuAdaptableParameters(self):
        return self.adaptable_parameters_dict

    def setAdaptableParameters(self, program_name, uniform_name, params, value):
        """
        params : Parameters name (str)
        value : float or anything...
        """
        if DEBUG:
            print("Params", params, "set to value", value, "for programs", program_name)

        self.adaptable_parameters_dict[program_name][uniform_name][params]["value"] = (
            value
        )

    ###########################################

    ###################
    # Uniforms Things #
    ###################
    def initUniformsForProgram(self, _file, program_name, reload=False):
        self.programs_uniforms.addProgram(_file, program_name, reload=False)

    def initUniformsBinding(self, binding, program_name):
        self.programs_uniforms.initBinding(program_name, binding, False)

    def reloadUniformsBinding(self, binding, program_name):
        """
        For reloading purpose
        """
        self.programs_uniforms.initBinding(program_name, binding, True)

    def reloadPreviousUniformsState(self):
        """
        When reloading purpose failed
        """
        self.programs_uniforms.reloadPreviousUniformsState()

    def restoreUniformsBinding(self, bindings):
        """
        Deserialize purpose
        """
        self.programs_uniforms.restoreUniformsBinding(bindings)

    def getUniformsBinding(self):
        return self.programs_uniforms.getUniformsBinding()

    def addProtectedUniforms(self, uniforms_name):
        self.programs_uniforms.addProtectedUniforms(uniforms_name)
        self.protectAdaptableParameters(uniforms_name)

    def bindUniform(self, af):
        self.already_called = True

        try:
            self.program["iResolution"] = self.win_size
        except Exception:
            pass

    def isCalled(self):
        self.already_called = True

    #########################
    def render(self, *args):
        raise NotImplementedError


class UniformsLookup:
    """
    Uses when we need to expose the uniforms (GUI purpose)
    self.uniforms for the GUI
    self._all_bindings for serialization purposes
    """

    def __init__(self, uniforms, callback, protected):
        self.protected = protected
        self._all_bindings = None
        self.uniforms = self.protect(uniforms)
        self.callback = callback

    def protect(self, uniforms):
        uniforms_copy = copy.deepcopy(uniforms)

        if DEBUG:
            print("Lookup uniforms :", uniforms)

        self._all_bindings = copy.deepcopy(uniforms)

        for program in uniforms_copy.keys():
            for to_protect in self.protected:
                if to_protect in uniforms_copy[program].keys():
                    del uniforms_copy[program][to_protect]

        return uniforms_copy

    def update(self, uniforms):
        del self._all_bindings
        del self.uniforms
        self.uniforms = self.protect(uniforms)

    def __getitem__(self, key):
        return self.uniforms[key]

    def __len__(self):
        return len(self.uniforms)

    def __iter__(self):
        return iter(self.uniforms)


class ProgramsUniforms:
    def __init__(self, parent=None):
        self.parent = parent
        self.init_binding = {}
        self.uniforms = {}
        self.programs = {}
        self.lookup = None
        self.protected = ["iResolution"]

    def addProgram(self, file, program_name, reload=False):
        """
        Add Uniforms for program 'program_name' by reading the file fragment programs
        if reload : store the previous state of uniforms binding before reloading it
        """
        if reload:
            self.previous_programs = self.programs
            self.previous_uniforms = self.uniforms
            self.programs = {}
            self.uniforms = {}

        self.uniforms[program_name] = {}
        self.programs[program_name] = getattr(self.parent, program_name + "program")
        file_lines = file.split(";")

        for line in file_lines:
            if "uniform" in line:
                tmp = line.split(" ")
                uniform_name = tmp[2]
                type = None
                self.addUniform(program_name, uniform_name, type)

    def addUniform(self, program_name, uniform_name, type_name):
        """
        Add the uniforms 'uniform_name' in the uniforms dictitonnary
        """
        self.uniforms[program_name][uniform_name] = {
            "type": type_name,
            "param_name": None,
        }

        if uniform_name not in self.protected:
            self.parent.initUniformsAdaptableParameters(
                program_name + "program", uniform_name
            )

    def addProtectedUniforms(self, uniforms_name):
        """
        Add protected uniforms (protect from binding change)
        """
        self.protected += uniforms_name

    def getUniformsBinding(self):
        """
        Get the uniforms binding in order to expose it (without protected uniforms)
        """
        if self.lookup is None:
            self.lookup = UniformsLookup(
                self.uniforms, self.changeBinding, self.protected
            )
        else:
            self.lookup.update(self.uniforms)

        return self.lookup

    def initBinding(self, program_name, binding, reload=False):
        """
        Initialize the binding (params to uniforms) for program 'program_name'
        """
        if reload:
            self.uniforms[program_name] = self.init_binding[program_name]
            return

        uniforms = self.uniforms[program_name]

        for uniform_name, param_name in binding.items():
            if DEBUG:
                print(uniforms)
                print(uniform_name, param_name)

            uniforms[uniform_name]["type"] = None
            uniforms[uniform_name]["param_name"] = param_name

        self.init_binding[program_name] = copy.deepcopy(uniforms)

    def reloadPreviousUniformsState(self):
        """
        Reload the previous state of binding (use when the program is reloaded)
        """
        del self.uniforms
        del self.programs
        self.uniforms = self.previous_uniforms
        self.program = self.previous_programs

    def changeBinding(self, program_name, uniform_name, param_name, type):
        """
        Change the binding of uniform 'uniform_name' to the parameters 'param_name'
        if type is 'audio_features' it will look in the audio_features dict to get it
        """
        if param_name == "default":
            uniforms = self.uniforms[program_name]
            uniforms[uniform_name]["type"] = None
            uniforms[uniform_name]["param_name"] = self.init_binding[program_name][
                uniform_name
            ]["param_name"]
        else:
            uniforms = self.uniforms[program_name]
            uniforms[uniform_name]["type"] = type if type == "audio_features" else None
            uniforms[uniform_name]["param_name"] = param_name

    def restoreUniformsBinding(self, bindings):
        """
        For deserialize purpose only
        """
        self.uniforms = bindings

    def bindUniformToProgram(self, audio_features, program_name=""):
        """
        bind all the uniforms to the program 'program_name' for rendering
        """
        program = self.programs[program_name]

        if DEBUG:
            print(
                "Bind uniforms to program :",
                program,
                "with name",
                program_name,
                "for node",
                self.parent.__class__.__name__,
            )

        for uniform_name, info in self.uniforms[program_name].items():
            if info["param_name"] is not None:  # ie if this uniform is set to a params
                if uniform_name not in self.protected:
                    if info["type"] == "audio_features":
                        if audio_features is not None:
                            data = audio_features[info["param_name"]]
                    else:
                        data = getattr(self.parent, info["param_name"])

                    modified_data = self.parent.getAdaptableEvaluationForUniform(
                        program_name + "program", uniform_name, data
                    )

                    if DEBUG:
                        print(
                            "ProgramUniform::bindUniformToProgram Trying to bind parameters",
                            info["param_name"],
                            "with value",
                            modified_data,
                            "to uniform",
                            uniform_name,
                            "in program",
                            program_name + "program",
                            " for node ",
                            self.parent.__class__.__name__,
                        )

                    program[uniform_name] = modified_data
                else:
                    data = getattr(self.parent, info["param_name"])

                    if isinstance(data, np.ndarray):
                        program[uniform_name].write(data)
                    else:
                        program[uniform_name] = data
