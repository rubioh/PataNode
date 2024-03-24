import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Scene
from node.node_conf import register_node


OP_CODE_EYE = name_to_opcode('eye')

@register_program(OP_CODE_EYE)
class Eye(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Eye"

        self.initProgram()
        self.initFBOSpecifications()
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
        frag_path = join(dirname(__file__), "eye.glsl")
        self.program = self.loadProgramToCtx(vert_path, frag_path, reload)
        if not reload:
            self.vbo = self.ctx.buffer(get_square_vertex_data())
        self.vao = self.ctx.vertex_array(self.program, [(self.vbo, "2f", "in_position")])
    
    def initParams(self):
        self.initAdaptableParameters("vitesse", .4)
        self.offset = 0
        self.initAdaptableParameters("intensity", 5, minimum=0, maximum=20)
        self.smooth_fast = 0
        self.time = 0
        self.tf = 0
        self.eslow = .4
        self.emid = .2

    def getParameters(self):
        return self.adaptableParametersDict

    def updateParams(self, af=None):
        self.vitesse = np.clip(self.vitesse, 0, 2)
        self.intensity = np.clip(self.intensity, 2, 10)
        self.time += 1 / 60 * (1 + self.vitesse)
        self.tf += 0.01
        if af is None:
            return
        self.smooth_fast = self.smooth_fast * 0.2 + 0.8 * af["full"][3]
        if af["full"][1] < 1.0 or af["full"][2] < 0.7:
            self.vitesse += 0.01
            self.intensity += 0.05
            if self.time > 500 and self.vitesse > 1.5:
                self.time = 0
                self.tf = 0
        else:
            self.vitesse -= 0.04
            self.intensity -= 0.1
        self.vitesse = np.clip(self.vitesse, 0, 2)
        self.intensity = np.clip(self.intensity, 2, 10)
        self.time += 1 / 60 * (1 + self.vitesse)
        self.tf += 0.01
        self.eslow = af["full"][1] * .75
        self.emid = af["low"][2] / 2.

    def bindUniform(self, af):
        super().bindUniform(af)
        self.program["iTime"] = self.time
        self.program["energy_fast"] = self.smooth_fast / 2.0
        self.program["energy_slow"] = self.eslow
        self.program["energy_mid"] = self.emid
        self.program["tf"] = self.tf
        self.program["intensity"] = self.intensity
        self.program["scale"] = 16 + 8 * np.cos(time.time() * 0.1)

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_EYE)
class EyeNode(ShaderNode, Scene):
    op_title = "Eye"
    op_code = OP_CODE_EYE
    content_label = ""
    content_label_objname = "shader_eye"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.shader_node_type = dirname(__file__).split('/')[-2]
        self.program = Eye(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()


    def render(self):
        return self.program.render()
