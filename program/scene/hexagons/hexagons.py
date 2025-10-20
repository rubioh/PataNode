from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_HEXAGONS = name_to_opcode("Hexagons")


@register_program(OP_CODE_HEXAGONS)
class Hexagons(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Hexagons"

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
        frag_path = join(dirname(__file__), "hexagons.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.time = 0
        self.rotation = 0.0
        self.rotationSpeed = 1.0
        self.offsetSpeed = 1.0
        self.waveFrequency = 1.0
        self.waveSpeed = 1.0
        self.numLayer = 2.0
        self.waveOffset = 0.0
        self.res = 1.0
        self.thickness = 0.0

    def initUniformsBinding(self):
        binding = {
            "iTime": "time",
            "rotationSpeed": "rotationSpeed",
            "offsetSpeed": "offsetSpeed",
            "waveFrequency": "waveFrequency",
            "waveSpeed": "waveSpeed",
            "numLayer": "numLayer",
            "waveOffset": "waveOffset",
            "res": "res",
            "thickness": "thickness",
        }
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def updateParams(self, af=None):
        if af is None:
            return
        self.time = af["time"] / 30.0

    #       self.waveOffset = self.waveOffset + af["low"][0];

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


@register_node(OP_CODE_HEXAGONS)
class HexagonsNode(ShaderNode, Scene):
    op_title = "Hexagons"
    op_code = OP_CODE_HEXAGONS
    content_label = ""
    content_label_objname = "shader_Hexagons"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Hexagons(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)

        return output_texture
