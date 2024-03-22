import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, load_program
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode
from node.node_conf import register_node

OP_CODE_SCREEN = 0

@register_program(OP_CODE_SCREEN)
class Screen(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Screen"

        self.initProgram()
        self.initParams()


    def initProgram(self, init_vbo=True):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "screen.glsl")
        vert = open(vert_path, 'r').read()
        frag = open(frag_path, 'r').read()
        self.program = load_program(self.ctx, vert, frag)
        if init_vbo:
            self.vbo = self.ctx.buffer(get_square_vertex_data())
        self.vao = self.ctx.vertex_array(self.program, [(self.vbo, "2f", "in_position")])

    def initParams(self):
        pass

    def updateParams(self, af):
        pass

    def bindUniform(self, af):
        super().bindUniform(af)
        _,_,w,h = self.ctx.screen.viewport
        self.program['iResolution'] = (w,h)
        self.program["tex"] = 0

    def render(self, texture, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        texture.use(0)
        self.ctx.screen.use()
        self.vao.render()

@register_node(OP_CODE_SCREEN)
class ScreenNode(ShaderNode):
    op_title = "Screen"
    op_code = OP_CODE_SCREEN
    content_label = ""
    content_label_objname = "output_screen"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[])
        self.program = Screen(ctx=self.scene.ctx)
        self.program.output_fbo = self.scene.ctx.screen
        self.gl_widget = self.scene.app.gl_widget
        self.eval()

    def restoreFBODependencies(self):
        self.scene.fbo_manager.restoreFBOUsability()
        for node in self.scene.nodes:
            node.markDirty()
        self.eval()

    def evalImplementation(self):
        input_node = self.getInput(0)
        if not input_node:
            self.grNode.setToolTip("Input is not connected")
            self.markDirty()
            return False

        success_eval = input_node.eval()

        if not success_eval:
            self.grNode.setToolTip("Input is NaN")
            self.markDirty()
            return False

        success_render = self.render()
        self.markInvalid(not success_render)
        self.markDirty(not success_render)
        self.grNode.setToolTip("")
        return True

    def render(self):
        input_node = self.getInput(0)
        if input_node is None:
            return False
        texture = input_node.render()
        self.program.render(texture)
        return True
