from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode
from matplotlib.colors import rgb_to_hsv, hsv_to_rgb
import numpy as np

OP_CODE_FRACTAL = name_to_opcode("fractal")


@register_program(OP_CODE_FRACTAL)
class Fractal(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Fractal"

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
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "fractal.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "main.glsl")
        self.loadProgramToCtx(vert_path, frag_path, False, name="oui_")

    def initUniformsBinding(self):
        binding = {
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms([])

    def initParams(self):
        self.smooth_fast = 0
        self.mode = 1
        self.K = 2
        self.Kmax = 10
        self.Kmin = 0
        self.sens = 1

        self.color_a = np.array([0.7, 0.4, 0.1])
        self.color_b = np.array([1.0, 0.8, 0.7])
        self.color_c = np.array([0.0, 0.0, 0.0])
        self.color_d = np.array([0.9, 0.1, 0.5])
        tmp = rgb_to_hsv(self.color_d)
        tmp[0] += 0.2
        self.color_d = hsv_to_rgb(tmp)
        self.time = np.float32([0])
        self.t_high = np.float32([0])

        self.decaying_kick_slow = 0.0

    def getParameters(self):
        return self.adaptableParametersDict

    def updateParams(self, fa=None):
        self.smooth_fast = self.smooth_fast * 0.5 + 0.5 * fa["full"][3]
        if fa["on_kick"]:
            self.update_color()
            self.K += 1 * self.sens
            if self.K > self.Kmax or self.K < 1:
                self.sens *= -1

        self.decaying_kick_slow += np.sqrt(fa["smooth_low"]) * 1.0 / 20.0
        self.decaying_kick_slow = self.decaying_kick_slow % 1

        if fa["on_chill"]:
            self.sens = -1
            self.K -= 0.1
            self.Kmin = 0.0
        else:
            self.Kmin = 10.0

        self.K = np.clip(self.K, self.Kmin, self.Kmax)

        self.time += (fa["low"][0] - 1) * 2
        self.t_high += fa["smooth_high"] / 2.0

    def update_color(self):
        tmp = rgb_to_hsv(self.color_a)
        tmp[0] += 0.00012
        self.color_a = hsv_to_rgb(tmp)

        tmp = rgb_to_hsv(self.color_b)
        tmp[0] += 0.00011
        self.color_b = hsv_to_rgb(tmp)

        tmp = rgb_to_hsv(self.color_c)
        tmp[0] += 0.0001
        self.color_c = hsv_to_rgb(tmp)

        tmp = rgb_to_hsv(self.color_d)
        tmp[0] += 0.0017
        self.color_d = hsv_to_rgb(tmp)

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, fa=None):
        af = fa
        if not fa:
            return
        self.oui_program["iTime"] = fa["time"] / 2.0 + self.time / 2.0
        self.oui_program["energy_fast"] = self.smooth_fast
        # self.oui_program['t_high'] = self.t_high
        self.oui_program["energy_slow"] = fa["full"][1]
        self.oui_program["energy"] = fa["smooth_low"] * 2 * np.pi
        self.oui_program["decaying_kick_slow"] = self.decaying_kick_slow
        self.oui_program["K"] = self.K
        self.oui_program["iResolution"] = self.win_size

        self.program["iChannel0"] = 10
        self.program["iMouse"] = [0.5, 0.5]
        self.program["iResolution"] = self.win_size

        try:
            self.program["color_a"] = self.color_a
        except:
            pass
        try:
            self.program["color_b"] = self.color_b
        except:
            pass
        try:
            self.program["color_c"] = self.color_c
        except:
            pass
        try:
            self.program["color_d"] = self.color_d
        except:
            pass
        self.program["energy"] = fa["smooth_low"] * 10.0
        self.updateParams(af)
        self.update_color()

        self.fbos[1].use()
        self.oui_vao.render()
        self.fbos[1].color_attachments[0].use(10)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_FRACTAL)
class FractalNode(ShaderNode, Scene):
    op_title = "Fractal"
    op_code = OP_CODE_FRACTAL
    content_label = ""
    content_label_objname = "shader_Fractal"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Fractal(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()

        return self.program.render(audio_features)
