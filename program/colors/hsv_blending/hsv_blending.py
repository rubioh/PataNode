import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Colors
from node.node_conf import register_node


OP_CODE_HSVBLENDING = name_to_opcode('hsvhsvhsvblending')

@register_program(OP_CODE_HSVBLENDING)
class HSVBlending(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "HSV Blending"

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
        frag_path = join(dirname(__file__), "hsv_blending.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 1
        self.GradientMap = 2
        self.hue_offset = 0
        self.iTime = 0
        self.saturation_offset = 0
        self.value_offset = 0

    def initUniformsBinding(self):
        binding = {
            'iResolution' : 'win_size',
            'iTime' : 'iTime',
            'iChannel0' : 'iChannel0',
            'GradientMap' : 'GradientMap',
            'hue_offset' : 'hue_offset',
            'saturation_offset' : 'saturation_offset',
            'value_offset' : 'value_offset'
        }
        super().initUniformsBinding(binding, program_name='')
        self.addProtectedUniforms(['iChannel0', 'GradientMap'])

    def updateParams(self, af):
        if af is None:
            return
        self.iTime = af['time']

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        textures[0].use(1)
        textures[1].use(2)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_HSVBLENDING)
class HSVNode(ShaderNode, Colors):
    op_title = "HSV Blending"
    op_code = OP_CODE_HSVBLENDING
    content_label = ""
    content_label_objname = "shader_hsv_blending"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1,2], outputs=[3])
        self.program = HSVBlending(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()
        input_nodes = self.getShaderInputs()
        if len(input_nodes) < 2:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        vel = input_nodes[1].render(audio_features)
        if texture is None or vel is None:
            return self.program.norender()
        output_texture = self.program.render([texture, vel], audio_features)
        return output_texture

