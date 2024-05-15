import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Scene
from node.node_conf import register_node

OP_CODE_RR = name_to_opcode('rainbow_rewqeqoad')

@register_program(OP_CODE_RR)
class RainbowRoad(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        
        super().__init__(ctx, major_version, minor_version, win_size)
        self.winsize = win_size
        self.title = "rainbow_road"
        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, 'f4']
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "RR.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initUniformsBinding(self):
        binding = {
                'iTime': 'iTime',
                'iResolution' : 'win_size',
                'energy':'energy',
                'energy_fast':'energy_fast',
                'energy_fast2':'energy_fast2',
                'energy_mid':'energy_mid',
                'energy_slow':'energy_slow',
                'turfu':'turfu',
                'tic_tile':'tic_tile',
                'mode':'mode',
                'c1':'c1',
                'trigger':'trigger'
                }
        super().initUniformsBinding(binding, program_name='')
        self.addProtectedUniforms([])

    def initParams(self):
        self.count = 0
        self.iTime = 0
        self.iResolution = self.winsize
        self.current_mean = 0.2
        self.vitesse = 0.7
        self.offset = 0
        self.smooth_fast = 0
        self.smooth_mid = 0
        self.smooth_tmp = 0
        self.turfu = 0
        self.tac = 0
        self.tic_tile = 0
        self.tic_tile2 = 0
        self.r = 0
        self.wait = 0
        self.tac = 0
        self.c1 = 0
        self.mode = 1
        self.time_au = 0
        self.trigger = np.zeros(4)
        self.time = np.array([0], dtype=np.float32)
        self.on_chill = 0
        self.count_kick = 0
        self.energy_fast = 0
        self.energy_fast2 = 0
        self.energy_slow = 0
        self.energy_mid = 0
        self.energy = 0

    def updateParams(self, fa):
        if fa is None:
            return
        self.smooth_fast = self.smooth_fast * 0.2 + 0.8 * fa["full"][3]
        self.smooth_mid = self.smooth_mid * 0.2 + 0.8 * fa["full"][2]
        tmp = max(self.smooth_fast - self.smooth_mid * 0.95, 0.0) * 10.0
        self.smooth_tmp = 0.1 * self.smooth_tmp + 0.9 * tmp

        self.trigger += 4 / fa["bpm"] * 2 * np.pi

        self.tac += 0.1
        self.tic_tile += 1.5

        if fa["on_kick"]:
            self.count_kick += 1
            self.tic_tile2 = 1
            self.tic_tile2 = self.tic_tile2 % 2
            if self.mode == 1:
                self.r = np.random.randint(0, 100)
            if self.count_kick >= 16:
                self.count_kick = 0
                self.c1 ^= 1

        if not fa["on_chill"] and self.on_chill:
            self.count_kick = 0

        if fa["on_chill"]:
            self.on_chill = 1
            self.c1 = 0
            self.turfu += 0.01
        else:
            self.on_chill = 0
            self.turfu -= 0.01

        self.turfu = np.clip(self.turfu, 0.3, 0.9)

        self.time += (
            (
                fa["bpm"] / 60 / 60 * 2.0 * np.pi
                + (fa["full"][2] / 2.0) ** 2
                + fa["bpm"] * (np.abs(1.0 - self.mode)) / 1000
            )
            / 2.0
        ) / 4

        self.iTime = fa["time"] / 2 + self.time
        self.energy_fast = fa["decaying_kick"] + 1.0
        self.energy_fast2 = fa["low"][3] / 2.0
        self.energy_slow = fa["full"][1] / 2.0
        self.energy_mid = max(fa["full"][3] - fa["full"][2] * 0.95, 0.0)
        self.energy = fa["full"][0] * 0.3
        self.mode = self.mode
        self.trigger= self.trigger
        self.turfu = self.turfu
        self.tic_tile = self.tic_tile
        self.c1 = self.c1

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def render(self, af):
        self.updateParams(af)
        self.bindUniform(af)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self, af):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_RR)
class RRNode(ShaderNode, Scene):
    op_title = "Rainbow road"
    op_code = OP_CODE_RR
    content_label = ""
    content_label_objname = "shader_rr"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = RainbowRoad(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)
        return output_texture
