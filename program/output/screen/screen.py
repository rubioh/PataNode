import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program
from program.program_base import ProgramBase
from program.colors.predominant_color.predominant_color import PredominantColorNode

from node.shader_node_base import ShaderNode, Output
from node.node_conf import register_node
from earcut.earcut import earcut

OP_CODE_SCREEN = 0

def read_file(path):
    f = open(path, "r")
    return f.read()

@register_program(OP_CODE_SCREEN)
class Screen(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Screen"

        self.initProgram()
        self.initParams()

    def initProgram(self, reload=False):
        vert_path = join(dirname(__file__), "screen_vtx.glsl")
        frag_path = join(dirname(__file__), "screen.glsl")
        code_version = "#version "
        code_version += (
            str(3) + str(3) + str("0 core\n")
        )
        self.program = self.ctx.program(
            vertex_shader=read_file(vert_path), fragment_shader=read_file(frag_path)
        )

    def initParams(self):
        pass

    def updateParams(self, af):
        pass

    def bindUniform(self, af):
        super().bindUniform(af)
        _,_,w,h = self.ctx.screen.viewport
        self.program['iResolution'] = (w,h)
        self.program["tex"] = 0

    def triangulate_poly(self, poly):
        pointlist = []
        for point in poly.pointlist:
            pointlist.append(point.x())
            pointlist.append(point.y())
        indices = earcut(pointlist)
        return indices

    def render_map(self, textures, af, polymap):
        for poly in polymap:
            vertex_pos = []
            vertex_tcs = []
            indices = self.triangulate_poly(poly)
            for i in indices:
                p = poly.pointlist[i]
                vertex_pos.append( (2. * p.x()) / 1280. )
                vertex_pos.append( (2. * p.y()) / 720. )
                vertex_tcs.append(p.tx)
                vertex_tcs.append(p.ty)
            vertex_pos = np.array(vertex_pos, 'f4')
            vertex_tcs = np.array(vertex_tcs, 'f4')

            vbo_p = self.ctx.buffer(vertex_pos)
            vbo_t = self.ctx.buffer(vertex_tcs)
            self.vao = self.ctx.vertex_array(self.program,
                [(vbo_p, "2f", "in_position"),
                (vbo_t, "2f", "in_tcs")])
            self.updateParams(af)
            self.bindUniform(af)
            textures[0].use(0)
            self.ctx.screen.use()
            self.vao.render()

    def render(self, textures, af=None, polymap = None):
        if polymap != None:
            self.render_map(textures, af, polymap)
            return True
        self.updateParams(af)
        self.bindUniform(af)
        textures[0].use(0)
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
        self.plreturn = None
        self.buffer_col = None
        self.eval()

    def restoreFBODependencies(self):
        self.scene.fbo_manager.restoreFBOUsability()
        for node in self.scene.nodes:
            node.markDirty()
            if (node != self):
                node.restoreFBODependencies()
        self.eval()

    def evalImplementation(self):
        input_node = self.getInput(0)
        if not input_node:
            self.grNode.setToolTip("Input is not connected")
            self.markDirty()
            return False

        input_texture = input_node.eval()

        if input_texture is None or not input_texture:
            self.grNode.setToolTip("Input is NaN")
            self.markDirty()
            return False
        success_render = self.program.render([input_texture])
        self.markInvalid(not success_render)
        self.markDirty(not success_render)
        self.grNode.setToolTip("")
        return True

    def render(self, audio_features=None, polymap = None):
        for node in self.scene.nodes:
            if isinstance(node, ShaderNode):
                node.program.already_called = False
            if isinstance(node, PredominantColorNode):
                self.plreturn = node
        input_nodes = self.getShaderInputs()
        if not len(input_nodes):
            return False
        texture = input_nodes[0].render(audio_features)
        if self.plreturn is not None:
            self.buffer_col = self.plreturn.render(texture)
        self.program.render([texture], audio_features, polymap)
        return True
