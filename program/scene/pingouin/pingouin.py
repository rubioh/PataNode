import numpy as np

from os.path import dirname, join

from matplotlib.colors import rgb_to_hsv, hsv_to_rgb

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_PINGOUIN = name_to_opcode("Pingouin")


@register_program(OP_CODE_PINGOUIN)
class Pingouin(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Pingouin"

        self.initProgram()
        self.initFBOSpecifications()
        self.initParams()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [[self.win_size, 4, "f4"]]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Pingouin.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.iTime = 0.0
        self.go_x = 0.0
        self.wait = 0
        self.iResolution = self.win_size
        self.energy = 0.0
        self.smooth_fast = 0.0
        self.energy_fast = 0.0
        self.energy_mid = 0.0
        self.energy_slow = 0.0
        self.energy_low = 0.0
        self.decaying_kick = 0.0
        self.move_x = 0.0
        self.move_z = 0.0
        self.sens_x = 0.0
        self.on_tempo = 0.0
        self.on_tempo2 = 0.0
        self.on_tempo4 = 0.0
        self.mode = 0.0
        self.angle_t = 0.0
        self.y_t = 0.0
        self.trigger = 0.0
        self.rot_final = 0.0
        self.on_chill = 0.0
        self.sens_x = -1.0
        self.sens_z = 1.0
        self.go_z = 1
        self.count = 0
        self.decaying_kick_slow = 0
        self.color = np.array([0.6, 0.6, 0.8])
        self.l = np.zeros(3)
        self.min_dist = 2

    def initUniformsBinding(self):
        binding = {
            "iTime": "iTime",
            "iResolution": "iResolution",
            "energy_fast": "energy_fast",
            "energy_slow": "energy_slow",
            "decaying_kick": "decaying_kick",
            "move_x": "move_x",
            "move_z": "move_z",
            "on_tempo": "on_tempo",
            "on_tempo2": "on_tempo2",
            "on_tempo4": "on_tempo4",
            "l": "l",
            "mode": "mode",
            "color": "color",
            "angle_t": "angle_t",
            "y_t": "y_t",
            "trigger": "trigger",
            "rot_final": "rot_final",
            "min_dist": "min_dist",
            "on_chill": "on_chill",
        }
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def updateParams(self, fa):
        if not fa:
            return

        self.smooth_fast = 0.5 * self.smooth_fast + 0.5 * fa["full"][3]

        if fa["decaying_kick"] and not fa["on_chill"]:
            self.decaying_kick_slow += 1 / 30

        self.decaying_kick_slow = self.decaying_kick_slow % 1

        if self.mode == 1:
            self.move_z += (fa["smooth_low"] * 1.5 + 0.02) * self.sens_z * self.go_z
            self.move_z = self.move_z % (6 * 100)
            self.move_x += (fa["smooth_low"] * 1.5 + 0.02) * self.sens_x * self.go_x
            self.move_x = self.move_x % (6 * 100)

        if fa["mini_chill"]:
            self.on_chill = 1

        if self.on_chill > 0:
            if fa["on_kick"]:
                self.wait = 15
                self.on_chill -= 0.24

            if self.on_chill <= 0:
                self.wait = 3

        if fa["on_kick"]:
            tmp = rgb_to_hsv(self.color)
            tmp[0] += 0.05
            self.color = hsv_to_rgb(tmp)
            self.wait += 1

        if self.wait >= 16:
            self.wait = 0
            self.angle_t = self.rot_final
            self.trigger = 1.0

        if self.trigger:
            self.y_t = -0.5 * (0.5 - 0.5 * np.cos(2 * np.pi * self.count / 10))
            self.angle_t += np.pi / 2 / 10.0
            self.count += 1

        if self.count >= 10:
            go_z = 1 - self.go_z

            if self.go_z:
                self.sens_z *= -1

            go_x = 1 - self.go_x

            if self.go_x:
                self.sens_x *= -1

            self.go_z = go_z
            self.go_x = go_x

            self.trigger = 0.0
            self.count = 0

            self.rot_final += np.pi / 2

        if not self.trigger:
            self.decaying_kick = (1.0 - fa["decaying_kick"]) * np.pi
        else:
            self.decaying_kick = 0.0

        if self.mode < 1:
            self.wait = 15
            self.min_dist = 2.5

            if fa["on_kick"]:
                self.l[0] += 1.0 / 16
                self.l[2] += 1.0 / 8
                self.l[1] += 1.0 / 32
        else:
            self.min_dist = 2.5

        if self.l[1] > 1.0 and self.mode < 1:
            self.mode += 0.01
            self.mode = np.clip(self.mode, 0, 1)

        self.on_tempo4 = fa["on_tempo4"] * 2 * np.pi
        self.on_tempo2 = fa["on_tempo2"] * 2 * np.pi
        self.on_tempo = fa["on_tempo"] * 2 * np.pi
        self.on_chill = fa["on_chill"]
        self.energy_slow = fa["low"][1]
        self.energy_fast = self.smooth_fast
        self.l = np.floor(self.l)
        self.iTime = fa["time"]

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


@register_node(OP_CODE_PINGOUIN)
class PingouinNode(ShaderNode, Scene):
    op_title = "Pingouin"
    op_code = OP_CODE_PINGOUIN
    content_label = ""
    content_label_objname = "shader_pingouin"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Pingouin(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)

        return output_texture
