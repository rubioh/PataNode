import yaml

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_DIRECTIONALARCHE = name_to_opcode("directionalarche")


@register_program(OP_CODE_DIRECTIONALARCHE)
class DirectionalArche(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "DirectionalArche"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [[self.win_size, 4, "f4"]]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "directionalarche.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initUniformsBinding(self):
        binding = {
            "iTime": "time",
            "iResolution": "win_size",
            "width": "width",
            "radius": "radius",
            "y_offset": "y_offset",
            "x_offset": "x_offset",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms([])

    def initParams(self):
        self.vitesse = 0.4
        self.time = 0

        with open("resources/zozo_conf.yaml") as stream:
            arch_conf = yaml.safe_load(stream)["arch"]
            self.width = arch_conf["width"]
            self.radius = arch_conf["radius"]
            self.y_offset = arch_conf["y_offset"]
            self.x_offset = arch_conf["x_offset"]

    def getParameters(self):
        return self.adaptableParametersDict

    def updateParams(self, af=None):
        self.time += 0.01 * self.vitesse

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_DIRECTIONALARCHE)
class DirectionalArcheNode(ShaderNode, Scene):
    op_title = "DirectionalArche"
    op_code = OP_CODE_DIRECTIONALARCHE
    content_label = ""
    content_label_objname = "shader_directionalarche"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = DirectionalArche(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()

        return self.program.render(audio_features)
