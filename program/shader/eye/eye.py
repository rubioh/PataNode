import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, load_program
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode
from node.node_conf import register_node


OP_CODE_EYE = 1

@register_program(OP_CODE_EYE)
class Eye(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Eye"
        self.required_fbos = 1

        self.initProgram()
        self.initParams()

    def initProgram(self):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "eye.glsl")
        vert = open(vert_path, 'r').read()
        frag = open(frag_path, 'r').read()
        self.program = load_program(self.ctx, vert, frag)
        self.vbo = self.ctx.buffer(get_square_vertex_data())
        self.vao = self.ctx.vertex_array(self.program, [(self.vbo, "2f", "in_position")])

    def reloadProgram(self):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "eye.glsl")
        vert = open(vert_path, 'r').read()
        frag = open(frag_path, 'r').read()
        self.program = load_program(self.ctx, vert, frag)
        self.vao = self.ctx.vertex_array(self.program, [(self.vbo, "2f", "in_position")])

    def initParams(self):
        self.vitesse = 0.7
        self.offset = 0
        self.intensity = 5
        self.smooth_fast = 0
        self.time = 0
        self.tf = 0
        self.eslow = .4
        self.emid = .2

    def updateParams(self, af=None):
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
        self.program["iResolution"] = (self.ctx.screen.width, self.ctx.screen.height)
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
class EyeNode(ShaderNode):
    op_title = "Eye"
    op_code = OP_CODE_EYE
    content_label = ""
    content_label_objname = "shader_eye"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Eye(ctx=self.scene.ctx)
        self.eval()

    def evalImplementation(self):
        try:
            win_sizes = [self.program.win_size]
            components = [4]
            dtypes = ['f4']
            fbos = self.scene.fbo_manager.getFBO(
                win_sizes
            )
            self.program.connectFbos(fbos)

            self.markInvalid()
            self.markDirty()
            self.program.render()
            self.grNode.setToolTip("")
            return self.program.render()
        except AssertionError:
            print("Created fbos doesn't match the number of required fbos for %s"%self.program.__class__.__name__)
            self.grNode.setToolTip("No fbo's found")
            self.markInvalid()
            return False
        except:
            print('No output Fbo found for the program %s'%self.program.__class__.__name__)
            self.grNode.setToolTip("No fbo's found")
            self.markInvalid()
            return False

    def render(self):
        return self.program.render()
