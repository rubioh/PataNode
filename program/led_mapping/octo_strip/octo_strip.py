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


OP_CODE_OCTOSTRIP = name_to_opcode("octo_strip")


@register_program(OP_CODE_OCTOSTRIP)
class OctoStrip(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "WhiteScreen"
        self.num_kick = 0
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
        frag_path = join(dirname(__file__), "octo_strip.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.time = 0

    def initUniformsBinding(self):
        binding = {
            "iTime": "time",
            "num_kick": "num_kick",
        }
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def updateParams(self, af=None):
        if af is None:
            return
        if af["on_kick"] == 1:
            self.num_kick = self.num_kick + 1
        self.time += 1 / 60

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


@register_node(OP_CODE_OCTOSTRIP)
class OctoStripNode(ShaderNode, Scene):
    op_title = "octostrip"
    op_code = OP_CODE_OCTOSTRIP
    content_label = ""
    content_label_objname = "shader_octo_strip"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = OctoStrip(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)
        return output_texture
