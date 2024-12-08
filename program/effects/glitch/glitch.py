import numpy as np

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Effects
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_GLITCH = name_to_opcode("glitch")


@register_program(OP_CODE_GLITCH)
class Glitch(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Glitch"

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
        frag_path = join(dirname(__file__), "glitch.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 1
        self.smooth_low = 0
        self.sens = 1
        self.translate = np.array([0.0, 0.0])
        self.count = 0
        self.mode = 0

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "iChannel0": "iChannel0",
            "energy_low": "smooth_low",
            "sens": "sens",
            "mode": "mode",
            "translate": "translate",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0", "translate"])

    def updateParams(self, af):
        if af is None:
            return

        tmp = np.clip(af["low"][3] - af["low"][2], 0, 100000)
        self.smooth_low = (
            self.smooth_low * 0.5
            + 0.5 * tmp * 0.5
            + af["smooth_high"] * af["smooth_low"]
        )

        if af["on_kick"]:
            self.sens *= -1

            tmp = np.random.rand(1) * 2 * np.pi
            self.translate = np.array([np.cos(tmp), np.sin(tmp)]) * self.win_size[0] / 3

            self.count += 1
            self.count %= 16

            if self.count == 0:
                self.mode += 1
                self.mode %= 3

        if af["on_chill"]:
            self.count = 0

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        textures[0].use(1)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_GLITCH)
class GlitchNode(ShaderNode, Effects):
    op_title = "Glitch"
    op_code = OP_CODE_GLITCH
    content_label = ""
    content_label_objname = "shader_glitch"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = Glitch(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()

        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()

        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
