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


OP_CODE_ABSQRT = name_to_opcode("abstract_sqrt")


@register_program(OP_CODE_ABSQRT)
class AbstractSQRT(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Abstract SQRT"

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
        frag_path = join(dirname(__file__), "AbstractSQRT.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.current_mean = 0.2
        self.sens = 1
        self.accel = 0
        self.time = 0
        self.t_h = np.array([0], dtype="float32")
        self.tic = 0
        self.tc = 0
        self.offset = 0.4
        self.count_beat = 0
        self.thresh = 0.5
        self.sens_thresh = 1.0
        self.t_rot = 0
        self.nrj_fast = 0

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "iTime": "time",
            "count_beat": "count_beat",
            "thresh": "thresh",
            "energy_fast": "nrj_fast",
            "t_h": "t_h",
            "t_rot": "t_rot",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms([])

    def updateParams(self, af):
        if af is None:
            return
        self.nrj_fast = af["smooth_low"] * 2.0 + 0.2
        if af["full"][1] < 0.8:
            self.accel += 0.002
        else:
            self.accel -= 0.01
        self.accel = np.clip(self.accel, 0.0, 3)
        if af["on_snare"]:
            self.count_beat += 1
        if af["on_kick"] == 1:
            self.sens *= -1
            self.tic += 1
            if self.tic == 8:
                self.tic = 0
                self.offset *= -1
            self.thresh += 0.1 * self.sens_thresh
            if self.thresh >= 0.9:
                self.thresh = 0.9
                self.sens_thresh = -1
            if self.thresh <= 0.1:
                self.thresh = 0.1
                self.sens_thresh = 1
        self.tc += 0.001
        self.time += (
            (af["bpm"] / 60 * 2 * np.pi / 60 * 0.5 * np.cos(self.tc))
            * af["low"][1]
            * 0.25
        )

        self.t_h += (af["smooth_low"] * 0.5 + 0.05 * af["low"][1]) * self.sens * 0.25

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


@register_node(OP_CODE_ABSQRT)
class AbastractSQRTNode(ShaderNode, Scene):
    op_title = "Abstract SQRT"
    op_code = OP_CODE_ABSQRT
    content_label = ""
    content_label_objname = "shader_abstract_sqrt"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = AbstractSQRT(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)
        return output_texture
