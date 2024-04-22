import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Scene
from node.node_conf import register_node


OP_CODE_PHARMACY = name_to_opcode('Pharmacy')

@register_program(OP_CODE_PHARMACY)
class Pharmacy(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Pharmacy"
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, 'f4']
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "pharmacy.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.tick = 0
        self.iTime = 0.
        self.iResolution = self.win_size
        self.decaying_kick= 0.
        self.onTempo = 0.

    def initUniformsBinding(self):
        binding = {
                'iTime': 'iTime',
                'iResolution': 'iResolution',
                'tick': 'tick',
                'decaying_kick' : 'decaying_kick',
                'onTempo': 'onTempo'
                }
        super().initUniformsBinding(binding, program_name='')
        super().addProtectedUniforms(
                []
        )

    def updateParams(self, af):
        if af == None:
            return
        self.tick = af["low"][0]
        self.iTime = af["time"] / 16
        self.decaying_kick = af["decaying_kick"]
        self.onTempo = (1 - af["on_tempo4"]) * 2 * 3.1415

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

@register_node(OP_CODE_PHARMACY)
class PharmacyNode(ShaderNode, Scene):
    op_title = "Pharmacy"
    op_code = OP_CODE_PHARMACY
    content_label = ""
    content_label_objname = "shader_Pharmacy"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Pharmacy(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)
        return output_texture
