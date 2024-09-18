import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import (
    SQUARE_VERT_PATH,
    get_square_vertex_data,
    register_program,
    name_to_opcode,
)
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Scene
from node.node_conf import register_node

OP_CODE_PSYSPIN = name_to_opcode("psyspin")


@register_program(OP_CODE_PSYSPIN)
class PsySpin(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "psyspin"

        self.bwinsize = win_size
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "psyspin.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, "f4"],
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initUniformsBinding(self):
        binding = {
            "iTime": "iTime",
            "iResolution": "iResolution",
            "time_sym_rot": "time_sym_rot",
            "time_tunnel_depth": "time_tunnel_depth",
            "time_tunnel_rot": "time_tunnel_rot",
            "time_depth_mod": "time_depth_mod",
            "tunnel_wave_amp": "tunnel_wave_amp",
            "tunnel_wave_freq": "tunnel_wave_freq",
            "time_col_rotation": "time_col_rotation",
            "tunnel_wave_amp": "tunnel_wave_amp",
            "wave_time_freq": "wave_time_freq",
            "kick": "kick",
            "onTempo": "onTempo",
        }
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def initParams(self):
        self.iTime = 0.0
        self.iResolution = self.bwinsize
        self.time_sym_rot = 0.0
        self.time_tunnel_depth = 0.0
        self.time_tunnel_rot = 0.0
        self.time_depth_mod = 0.0
        self.tunnel_wave_amp = 0.0
        self.tunnel_wave_freq = 0.0
        self.time_col_rotation = 0.0
        self.wave_time_freq = 0.0
        self.t = 0
        self.G = 0.15
        self.kick = 0
        self.onTempo = 0
        self.smooth_square = 0

    def update_params(self, af):
        if not af:
            return

        tm = 0.01
        self.t += (self.smooth_square * 0.05 + af["low"][1] * 0.02) * 40 / 127 * 3.0
        self.smooth_square = (
            self.smooth_square * 0.5 + (af["low"][3] ** 3 - af["low"][1] ** 3) * 0.5
        )
        self.time_sym_rot = (af["time"] * tm * 10.0 + self.t / 10.0) * self.G
        self.time_tunnel_depth = (af["time"] * tm * 10.0) * self.G
        self.time_tunnel_rot = (
            af["time"] * tm * 20.0 + af["low"][3] * 21 / 127 * 0.1
        ) * self.G
        self.tunnel_wave_amp = (1.0 + af["smooth_low"] * 84 / 127 * 4.0) * self.G * 3
        self.time_depth_mod = (
            af["time"] * tm * -2.0 - self.tunnel_wave_amp / 39.0 + self.t / 30.0
        ) * self.G
        self.time_col_rotation = (-af["time"] * tm * -5.0) * self.G
        self.tunnel_wave_freq = 1.0 * self.G
        self.wave_time_freq = 1.0 * self.G
        onTempo = af["on_tempo"] * 3.14159
        self.kick = (
            min(max(af["full"][3] - 0.8 * af["full"][2], 0.05) * 0.8, 0.48) * self.G
        )
        self.iTime = af["time"] * self.G

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, af):
        self.update_params(af)
        self.bindUniform(af)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_PSYSPIN)
class PsySpinNode(ShaderNode, Scene):
    op_title = "Psy spin"
    op_code = OP_CODE_PSYSPIN
    content_label = ""
    content_label_objname = "shader_PsySpin"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = PsySpin(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)
        return output_texture
