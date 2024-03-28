import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Output
from node.node_conf import register_node

OP_CODE_SCREEN = 0

@register_program(OP_CODE_SCREEN)
class Screen(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Screen"

        self.initProgram()
        self.initParams()

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "screen.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

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
        return True

@register_node(OP_CODE_SCREEN)
class ScreenNode(ShaderNode, Output):
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
            node.program.fbos = None
        self.eval()

    def evalImplementation(self):
        input_node = self.getInput(0)
        if not input_node:
            self.grNode.setToolTip("Input is not connected")
            self.markDirty()
            return False

        input_texture = input_node.eval()

        if input_texture is None:
            self.grNode.setToolTip("Input is NaN")
            self.markDirty()
            return False

        success_render = self.program.render(input_texture)
        self.markInvalid(not success_render)
        self.markDirty(not success_render)
        self.grNode.setToolTip("")
        return True

    def render(self, audio_features=None):
        input_node = self.getInput(0)
        if input_node is None:
            return False
        texture = input_node.render(audio_features)
        self.program.render(texture, audio_features)
        return True
