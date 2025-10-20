import numpy as np

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_PATATRACK3D = name_to_opcode("patatrack3D!")


@register_program(OP_CODE_PATATRACK3D)
class Patatrack3D(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Patatrack3D"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 3
        fbos_specification = [
            [self.win_size, 4, "f4"],
            [self.win_size, 4, "f4"],
            [self.win_size, 4, "f4"],
        ]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "sdf/sdf.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, "sdf_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "palette/palette.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, "palette_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "patatrack3d.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, "")

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "mini_chill": "mini_chill",
            "energy": "nrj",
            "mode": "mode",
            "mode_sym": "mode_sym",
            "tz": "tz",
            "tr": "tr",
            "tf": "tf",
            "th": "th",
        }
        super().initUniformsBinding(binding, program_name="sdf_")
        binding = {
            "iResolution": "win_size",
            "iChannel0": "iChannel0",
            "th": "th",
            "ts": "ts",
            "mode_ptt": "mode_ptt",
            "energy": "nrj",
        }
        super().initUniformsBinding(binding, program_name="palette_")
        binding = {
            "iResolution": "win_size",
            "iChannel0": "iChannel0",
            "energy": "nrj",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def initParams(self):
        self.iChannel0 = 0
        self.smooth_pitch = 0
        self.tz = 0
        self.tf = 0
        self.tr = 0
        self.th = 0
        self.ts = 0
        self.thp = 0
        self.mini_chill = 0
        self.prev_tz = 0
        self.go_kick = 0
        self.mode = 0
        self.mode_sym = 0
        self.count_beat = 0
        self.count_beat1 = 32
        self.count_kick = 0
        self.mode_ptt = 0
        self.go_ptt = 0
        self.sens_th = 1
        self.cval = 0
        self.nrj = 0
        self.time = 0

    def updateParams(self, af=None):
        if af is None:
            return

        self.time = af["time"]
        self.nrj = af["smooth_low"] ** 0.5

        if af["on_kick"]:
            self.prev_tz ^= 1

        self.tz = (self.prev_tz + af["decaying_kick"] ** 2.0) * 3.14159
        self.tr += af["smooth_low"] * 0.1 + 0.04
        self.tf += af["smooth_low"] * 0.5 + 0.05
        self.ts += (0.005 + af["low"][3] * 0.01) * 0.3
        self.mini_chill -= 0.04

        self.mode_ptt = 1
        self.th += (0.01 + af["smooth_low"] * 0.1) * 0.1
        self.th %= 2.0 * 3.14159

        if af["mini_chill"]:
            self.mini_chill += 0.08
            self.count_beat = 63
            self.count_beat1 = 31

        self.mini_chill = np.clip(self.mini_chill, 0, 1)

        if af["on_kick"]:
            self.count_kick += 1
            self.count_beat += 1
            self.count_beat1 += 1

            if self.count_beat >= 64:
                self.count_beat = 0
                self.mode_sym ^= 1

            if self.count_beat1 >= 64:
                self.count_beat1 = 0
                self.mode ^= 1

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")
        self.programs_uniforms.bindUniformToProgram(af, program_name="sdf_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="palette_")

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)

        self.fbos[0].use()
        self.sdf_vao.render()

        self.fbos[0].color_attachments[0].use(0)
        self.fbos[1].use()
        self.palette_vao.render()

        self.fbos[1].color_attachments[0].use(0)
        self.fbos[2].use()
        self.vao.render()
        return self.fbos[2].color_attachments[0]

    def norender(self):
        return self.fbos[2].color_attachments[0]


@register_node(OP_CODE_PATATRACK3D)
class Patatrack3DNode(ShaderNode, Scene):
    op_title = "Patatrack3D"
    op_code = OP_CODE_PATATRACK3D
    content_label = ""
    content_label_objname = "shader_patatrack3d"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Patatrack3D(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            return self.program.norender()

        return self.program.render(audio_features)
