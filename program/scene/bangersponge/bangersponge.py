from os.path import dirname, join
import numpy as np
from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_BANGERSPONGE = name_to_opcode("bangersponge")


@register_program(OP_CODE_BANGERSPONGE)
class BangerSponge(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "BangerSponge"

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
        frag_path = join(dirname(__file__), "bangersponge.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initUniformsBinding(self):
        binding = {
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms([])

    def initParams(self):
        self.dist = 0
        self.speed = 0
        self.cumulativ_smooth = 0.0

    def getParameters(self):
        return self.adaptableParametersDict

    def updateParams(self, fa):
        if not fa:
            return
        self.dist += (
            (fa["bpm"] / 60 / 60 * 2.0 * 3.14157 / 4.0 + (fa["full"][2] / 2.0) ** 2)
            / 211111.0
        ) / 24

        self.cumulativ_smooth += fa["smooth_full"] * 1.5
    def bindUniform(self, af):
        fa = af
        if not fa:
            return
        self.program["iTime"] = fa["time"] / 16
        self.program["dist"] = fa["time"] + self.dist
        self.program["energy_fast"] = fa["decaying_kick"] + 1.0
        self.program["energy_fast_cam"] = (
            np.cos(2.0 * fa["decaying_kick"] * 3.14) * 0.5 + 1.0
        )
        self.program["energy_fast2"] = fa["low"][3] / 2.0
        self.program["energy_slow"] = fa["full"][1] / 2.0
        self.program["energy_mid"] = max(
            fa["full"][3] - fa["full"][2] * 0.95, 0.0
        )
        self.program["energy"] = fa["full"][0] * 0.3
        self.program["onTempo"] = (1 - fa["on_tempo4"]) * 2 * 3.1415
        self.program["onKick"] = fa["on_kick"]
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


@register_node(OP_CODE_BANGERSPONGE)
class BangerSpongeNode(ShaderNode, Scene):
    op_title = "BangerSponge"
    op_code = OP_CODE_BANGERSPONGE
    content_label = ""
    content_label_objname = "shader_BangerSponge"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = BangerSponge(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()

        return self.program.render(audio_features)
