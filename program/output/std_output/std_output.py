import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import (
    SQUARE_VERT_PATH,
    get_square_vertex_data,
    register_program,
)
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Output
from node.node_conf import register_node

OP_CODE_STDOUTPUT = 1


@register_program(OP_CODE_STDOUTPUT)
class StdOutput(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Std Output"

        self.initProgram()
        self.initParams()
        self.initFBOSpecifications()

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "std_output.glsl")
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

    def initParams(self):
        pass

    def updateParams(self, af):
        pass

    def bindUniform(self, af):
        pass

    def render(self, textures, af=None):
        return textures[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_STDOUTPUT)
class StdOutputNode(ShaderNode, Output):
    op_title = "Std Output"
    op_code = OP_CODE_STDOUTPUT
    content_label = ""
    content_label_objname = "std_output"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[])
        self.program = StdOutput(ctx=self.scene.ctx)
        self.program.output_fbo = self.scene.ctx.screen
        self.gl_widget = self.scene.app.gl_widget
        self.eval()

    def restoreFBODependencies(self):
        for node in self.scene.nodes:
            if not isinstance(node, Output):
                node.restoreFBODependencies()
            node.markDirty()
            node.program.fbos = None
        self.eval()

    def render(self, audio_features=None):
        for node in self.scene.nodes:
            node.program.already_called = False
        input_nodes = self.getShaderInputs()
        if not len(input_nodes):
            return False
        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
