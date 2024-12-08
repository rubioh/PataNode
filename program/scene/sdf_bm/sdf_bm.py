import time
import numpy as np

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_SDFBM = name_to_opcode("SDF_BM")


@register_program(OP_CODE_SDFBM)
class SDF_BM(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Eye"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 2
        fbos_specification = [[self.win_size, 4, "f4"], [self.win_size, 4, "f4"]]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        # Info program
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Info/info.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="info_")

        # Normal program
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Normal/normal.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="normal_")

    def initUniformsBinding(self):
        binding = {
            "tm": "tma",
            "tz": "tza",
            "tp": "tp_final",
            "tptt": "tptt",
            "mode_sym": "mode_sym",
            "go_ptt": "go_ptt",
            "go_arms": "go_arms",
            "mode_ptt": "mode_ptt",
            "iResolution": "win_size",
        }
        super().initUniformsBinding(binding, program_name="info_")
        binding = {
            "iResolution": "win_size",
            "mode_ptt": "go_ptt",  # self.mode_ptt
            "iChannel0": "iChannel0",
            "go_idx": "go_bloom",
            "goBloom_arms": "goBloom_arms",
            "tc": "tc",
            "go_idx2": "go_bloom2",
        }
        super().initUniformsBinding(binding, program_name="normal_")
        self.addProtectedUniforms(["iChannel0"])

    def initParams(self):
        self.tm = 150
        self.tma = 150
        self.tz = 250
        self.tza = 250
        self.tp = 170
        self.tc = 280
        self.tptt = 0
        self.go_bloom = 0
        self.go_bloom2 = 0
        self.cnt_beat = 0
        self.mode2 = 1
        self.mode_sym = 0
        self.mode_ptt = 0
        self.sens = -1
        self.wait_mc = 0
        self.goBloom_arms = 0
        self.go_ptt = 0
        self.sens_ptt = 1
        self.sens_sym = 1
        self.wait_go_arms = 0
        self.go_arms = 0
        self.cnt_go_arms = 0
        self.cnt_full_ptt = 0
        self.tp_final = self.tp
        self.wait_to_ptt = 255
        self.iChannel0 = 1

    def updateParams(self, af):
        if af is None:
            self.tm = time.time() % 1000
            self.tz = time.time() % 1000
            self.tp = time.time() % 1000
            self.tc = time.time() % 1000
            self.tptt = time.time() % 1000
            return

        self.tm += 0.01
        self.tz += af["smooth_low"] * 0.1 + 1 / 60 * 0.2
        self.tp += af["smooth_low"] * 0.1 + 1 / 60 * 0.2
        self.tc += af["smooth_low"] * 0.1 + 1 / 60 * 0.2
        self.tptt += 1.0 / 60 + af["smooth_low"] * 0.03

        if af["on_kick"]:
            self.cnt_beat += 1
            self.go_bloom += 1 * self.sens

            if self.mode2 == 0:
                self.go_bloom2 = np.random.randint(-12, 12)

            if self.mode2 == 1:
                self.go_bloom2 = self.go_bloom - 2

            if self.go_bloom >= 12:
                self.sens = -1

            if self.go_bloom <= 0:
                self.sens = 1
                self.mode2 ^= 1

            if self.cnt_beat % 32 == 0:
                if self.mode_ptt <= 0:
                    self.sens_ptt = 1

                if self.mode_ptt >= 1:
                    self.sens_ptt = -1

#       self.mode_ptt += .01*self.sens_ptt
#       self.mode_ptt = np.clip(self.mode_ptt, 0, 1)

        if af["mini_chill"] and self.wait_mc > 10:
            self.wait_mc = 0
            self.go_bloom = np.random.randint(0, 12)

        if self.cnt_beat % 64 == 0:
            self.mode_sym += 0.02 * af["smooth_low"] * self.sens_sym

        if self.mode_sym % 1 != 0:
            self.mode_sym += 0.02 * af["smooth_low"] * self.sens_sym

            if self.mode_sym >= 1:
                self.mode_sym = 1
                self.sens_sym = -1

            if self.mode_sym <= 0:
                self.mode_sym = 0
                self.sens_sym = 1

        if af["mini_chill"] and self.wait_to_ptt > 255:
            self.go_ptt += 0.01
            self.wait_go_arms += 0.001
            self.go_bloom = -40
            self.go_ptt = np.clip(self.go_ptt, 0, 1)

        if self.go_ptt > 0:
            self.go_ptt += 0.01
            self.wait_go_arms += 0.002

            if self.cnt_go_arms < 32:
                self.go_bloom = -40

            self.go_ptt = np.clip(self.go_ptt, 0, 1)

        if self.wait_go_arms >= 1:
            self.wait_go_arms = 1

            if af["on_kick"]:
                self.go_arms ^= 1
                self.cnt_go_arms += 1

        if self.cnt_go_arms >= 32:
            if af["on_kick"]:
                self.mode_ptt = 1
                self.go_bloom = np.random.randint(2, 5)
                self.cnt_full_ptt += 1

        if self.cnt_full_ptt >= 32:
            self.go_ptt -= 0.02
            self.go_ptt = np.clip(self.go_ptt, 0, 1)
            self.go_arms = 0
            self.mode_ptt = 0

            if self.go_ptt == 0:
                self.go_arms = 0
                self.mode_ptt = 0
                self.wait_go_arms = 0
                self.cnt_go_arms = 0
                self.cnt_full_ptt = 0

            self.wait_to_ptt = 0

        if self.go_ptt == 0 and af["on_kick"]:
            self.wait_to_ptt += 1

        self.wait_mc += 1
        self.goBloom_arms = af["smooth_low"] ** 0.25 + 0.1
        self.mode_sym = 1

        self.tma = self.tm + af["smooth_low"] * 10.0 * 3.0
        self.tza = self.tz + af["smooth_high"] * 5.0 * 3.0

        self.tp_final = self.tp * 3

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="info_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="normal_")

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)

        self.fbos[0].clear()
        self.fbos[0].use()
        self.info_vao.render()

        self.fbos[1].clear()
        self.fbos[1].use()
        self.fbos[0].color_attachments[0].use(1)
        self.normal_vao.render()
        return self.fbos[1].color_attachments[0]

    def norender(self):
        return self.fbos[1].color_attachments[0]

        # self.apply_utils(self.manager.utils["Bloom2"])


@register_node(OP_CODE_SDFBM)
class SDF_BMNode(ShaderNode, Scene):
    op_title = "SDF_BM"
    op_code = OP_CODE_SDFBM
    content_label = ""
    content_label_objname = "shader_sdf_bm"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = SDF_BM(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()

        return self.program.render(audio_features)
