import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Utils
from node.node_conf import register_node

OP_CODE_SYMETRY = name_to_opcode('symetry')

@register_program(OP_CODE_SYMETRY)
class Symetry(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Symetry"

        self.initProgram()
        self.initFBOSpecifications()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, 'f4'],
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "symetry.glsl")
        self.program = self.loadProgramToCtx(vert_path, frag_path)
        if not reload:
            self.vbo = self.ctx.buffer(get_square_vertex_data())
        self.vao = self.ctx.vertex_array(self.program, [(self.vbo, "2f", "in_position")])

    def initParams(self):
        self.program["iChannel0"] = 1
        self.chill = False
        self.mode = 0
        self.t = 0
        self.t_angle = 0
        self.initAdaptableParameters("smlow", 1, minimum=0, maximum=10)
        #self.smlow = 1

    def updateParams(self, af=None):
        if af is None:
            return
        self.t += af["smooth_full"]
        if af["on_chill"] and not self.chill:
            self.chill = True

        if self.chill and not af["on_chill"]:
            self.mode ^= 1
            self.chill = False

        if af["on_chill"] == 0.0:
            self.t_angle += af["full"][0] * 0.01 * (2.5 * self.camp + 0.5) - 0.03

        self.smlow = af["smooth_low"] * (self.camp * 2.5 + .5)

    def bindUniform(self, af):
        super().bindUniform(af)
        self.program["smooth_low"] = self.smlow
        self.program["mode"] = self.mode
        self.program["t"] = self.t * 5.0
        self.program["t_angle"] = self.t_angle * 5.0

    def render(self, texture, af=None):
        self.bindUniform(af)
        texture.use(1)
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
        self.program = Symetry(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self):
        input_node = self.getInput(0)
        if input_node is None:
            return self.program.norender()
        texture = input_node.render()
        return self.program.render(texture)
