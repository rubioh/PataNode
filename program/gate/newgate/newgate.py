from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Gate
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_SQUAREGATE = name_to_opcode("squaregate")


@register_program(OP_CODE_SQUAREGATE)
class SquareGate(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "SquareGate"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, "f4"],
        ]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "squaregate.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 0
        self.iChannel1 = 1
        self.time = 0
        self.square_size = 0
        self.energy = 0
        self.N_SQUARE = 30
        self.border_size = 1

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "iTime": "time",
            "iChannel0": "iChannel0",
            "iChannel1": "iChannel1",
            "square_size": "square_size",
            "energy": "energy",
            "N_SQUARE": "N_SQUARE",
            "border_size": "border_size",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0", "iChannel1"])

    def updateParams(self, af):
        if af is None or self.already_called:
            return

        self.time += (af["smooth_low"] * 0.05 + 0.01) * 0.25
        self.square_size = af["low"][1] * 0.7 * 0.5
        self.energy = af["smooth_low"] * 3.0 + 0.5

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)

        textures[0].use(0)
        textures[1].use(1)

        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_SQUAREGATE)
class SquareGateNode(ShaderNode, Gate):
    op_title = "SquareGate"
    op_code = OP_CODE_SQUAREGATE
    content_label = ""
    content_label_objname = "shader_squaregate"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1, 1], outputs=[3])
        self.program = SquareGate(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()

        if len(input_nodes) == 0:
            return self.program.norender()

        if len(input_nodes) == 1:
            texture = input_nodes[0].render(audio_features)
            return texture

        texture1 = input_nodes[0].render(audio_features)
        texture2 = input_nodes[1].render(audio_features)
        output_texture = self.program.render([texture1, texture2], audio_features)
        return output_texture
