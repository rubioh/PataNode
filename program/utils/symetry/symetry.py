from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Utils
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_SYMETRY = name_to_opcode("symetry")


@register_program(OP_CODE_SYMETRY)
class Symetry(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Symetry"

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
        frag_path = join(dirname(__file__), "symetry.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initUniformsBinding(self):
        binding = {
            "iChannel0": "iChannel0",
            "smooth_low": "smlow",
            "mode": "symetry_mode",
            "t": "t_final",
            "t_angle": "t_angle_final",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def initParams(self):
        self.chill = False
        self.t = 0
        self.t_final = 0
        self.t_angle = 0
        self.t_angle_final = 0
        self.iChannel0 = 1
        self.smlow = 1
        self.rotation_amplification = 1
        self.energy_amplification = 1
#       self.initAdaptableParameters("rotation_amplification", 1, minimum=-5, maximum=5)
#       self.initAdaptableParameters("energy_amplification", 1, minimum=.5, maximum=5)
        self.automatic_mode = 1
        self.symetry_mode = 1
#       self.initAdaptableParameters("automatic_mode", 1, widget_type="CheckBox")
#       self.initAdaptableParameters("symetry_mode", 1, widget_type="CheckBox")

    def updateParams(self, af=None):
        if af is None:
            return

        self.t += af["smooth_full"]

        if af["on_chill"] and not self.chill:
            self.chill = True

        if self.automatic_mode:
            if self.chill and not af["on_chill"]:
                self.symetry_mode ^= 1
                self.chill = False

        if af["on_chill"] == 0.0:
            self.t_angle += (
                af["full"][0] * 0.01 * (2.5 * self.rotation_amplification + 0.5) - 0.03
            )

        self.smlow = af["smooth_low"] * (self.energy_amplification * 2.5 + 0.5)
        self.t_final = self.t * 5.0
        self.t_angle_final = self.t_angle * 5.0

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.bindUniform(af)
        self.updateParams(af)

        textures[0].use(1)

        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_SYMETRY)
class SymetryNode(ShaderNode, Utils):
    op_title = "Symetry"
    op_code = OP_CODE_SYMETRY
    content_label = ""
    content_label_objname = "shader_symetry"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = Symetry(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()

        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()

        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
