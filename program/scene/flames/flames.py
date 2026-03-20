import time

import numpy as np

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_FLAMES = name_to_opcode("flames")


@register_program(OP_CODE_FLAMES)
class Flames(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Flames"

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
        frag_path = join(dirname(__file__), "flames.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.time = 0
        self.freq = 1.0
        self.strength = 1.0
        self.anim = 1.0

    def initUniformsBinding(self):
        binding = {
            "iTime": "time",
            "freq": "freq",
            "strength": "strength",
            "anim": "anim",
        }
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def updateParams(self, af=None):
        if af is None:
            return
        self.time += 1.0 / 60.0

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


@register_node(OP_CODE_FLAMES)
class FlamesNode(ShaderNode, Scene):
    op_title = "Flames"
    op_code = OP_CODE_FLAMES
    content_label = ""
    content_label_objname = "shader_flames"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Flames(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)

        return output_texture
