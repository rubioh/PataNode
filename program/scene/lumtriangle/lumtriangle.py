import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Scene
from node.node_conf import register_node


OP_CODE_LUMTRIANGLE = name_to_opcode('lumtriangle')

@register_program(OP_CODE_LUMTRIANGLE)
class LumTriangle(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "LumTriangle"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

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
        frag_path = join(dirname(__file__), "lumtriangle.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initUniformsBinding(self):
        binding = {
                'x0': 'x0',
                'y0': 'y0',
                'energy_cum': 'energy_cum',
                'energy': 'energy',
                'zoom_factor' : 'zoom_factor'
                }

        super().initUniformsBinding(binding, program_name='')
        super().addProtectedUniforms(
                []
        )

    def initParams(self):
        self.zoom_factor = 1.
        self.energy_cum = 0
        self.x0 = 0
        self.y0 = 1
        self.count_beat = 0
        self.tc = 0
        self.gox = 1
        self.energy = 0

    def updateParams(self, af):
        if af is None:
            return
        self.energy = af["smooth_low"]
        self.energy_cum += af["smooth_low"] * 0.2 + 0.01
        self.energy_cum %= 10000
        if af["on_kick"]:
            self.count_beat += 1

        if self.count_beat > 64 and self.gox:
            self.tc += 0.0003 + af["smooth_low"] * 0.006
            if self.tc < 1:
                self.x0 = np.sin(self.tc * np.pi / 2)
            if self.tc > 1 and self.tc < 2:
                self.x0 = 1
                self.y0 = np.sin(self.tc * np.pi / 2)
            if self.y0 < 0.01:
                self.count_beat = 0
                self.gox ^= 1
                self.x0 = 1
                self.y0 = 0
                self.tc = 0
        elif self.count_beat > 64 and not self.gox:
            self.tc += 0.0003 + af["smooth_low"] * 0.006
            if self.tc < 1:
                self.y0 = np.sin(self.tc * np.pi / 2)
            if self.tc > 1 and self.tc < 2:
                self.y0 = 1
                self.x0 = np.sin(self.tc * np.pi / 2)
            if self.x0 < 0.01:
                self.count_beat = 0
                self.gox ^= 1
                self.y0 = 1
                self.x0 = 0
                self.tc = 0

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_LUMTRIANGLE)
class LumTriangleNode(ShaderNode, Scene):
    op_title = "LumTriangle"
    op_code = OP_CODE_LUMTRIANGLE
    content_label = ""
    content_label_objname = "shader_lumtriangle"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = LumTriangle(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)
        return output_texture
