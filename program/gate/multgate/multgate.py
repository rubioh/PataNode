import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Gate
from node.node_conf import register_node


OP_CODE_MULTGATE = name_to_opcode('multgate')

@register_program(OP_CODE_MULTGATE)
class MultGate(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "MultGate"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
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
        frag_path = join(dirname(__file__), "multgate.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 0
        self.iChannel1 = 1
        self.energy = 1
        self.drywet = 0

    def initUniformsBinding(self):
        binding = {
            'iResolution' : 'win_size',
            'iChannel0' : 'iChannel0',
            'iChannel1' : 'iChannel1',
            'energy' : 'energy',
            'drywet': 'drywet'
        }
        super().initUniformsBinding(binding, program_name='')
        self.addProtectedUniforms(['iChannel0', 'iChannel1'])

    def updateParams(self, af):
        if af is None or self.already_called:
            return

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        textures[0].use(0)
        textures[1].use(1)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_MULTGATE)
class MultGateNode(ShaderNode, Gate):
    op_title = "MultGate"
    op_code = OP_CODE_MULTGATE
    content_label = ""
    content_label_objname = "shader_multgate"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1,2], outputs=[3])
        self.program = MultGate(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if len(input_nodes) == 0:
            return self.program.norender()
        if len(input_nodes) == 1:
            texture = input_nodes[0].render(audio_features)
            return texture
        texture1 = input_nodes[0].render(audio_features)
        texture2 = input_nodes[1].render(audio_features)
        output_texture = self.program.render([texture1, texture2], audio_features)
        return output_texture

