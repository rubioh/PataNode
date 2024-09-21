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

from node.shader_node_base import ShaderNode, Physarum
from node.node_conf import register_node


OP_CODE_RGB2LAB = name_to_opcode("rgb2lab")


@register_program(OP_CODE_RGB2LAB)
class RGB2LAB(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "RGB2LAB"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, "f4"],
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "rgb2lab.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 1

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "iChannel0": "iChannel0",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def updateParams(self, af):
        if af is None:
            return
        pass

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        textures[0].use(1)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_RGB2LAB)
class RGB2LABNode(ShaderNode, Physarum):
    op_title = "RGB2LAB"
    op_code = OP_CODE_RGB2LAB
    content_label = ""
    content_label_objname = "shader_rgb2lab"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = RGB2LAB(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.already_called:
            return self.program.norender()
        self.already_called = True
        input_nodes = self.getShaderInputs()
        if not len(input_nodes):
            return self.program.norender()
        if input_nodes[0].already_called:
            texture = input_nodes[0].program.norender()
        else:
            texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
