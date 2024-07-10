import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Utils
from node.node_conf import register_node

import yaml


OP_CODE_MASKARCHE = name_to_opcode('maskarche')

@register_program(OP_CODE_MASKARCHE)
class MaskArche(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "MaskArche"

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
        frag_path = join(dirname(__file__), "maskarche.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initUniformsBinding(self):
        binding = {
            'iResolution': 'win_size',
            'iChannel0': 'iChannel0',
            'width': 'width',
            'radius': 'radius',
            'height': 'height'
        }
        super().initUniformsBinding(binding, program_name='')
        self.addProtectedUniforms(['iChannel0'])
    
    def initParams(self):
        self.vitesse = .4
        self.time = 0
        self.iChannel0 = 1
        with open("resources/zozo_conf.yaml") as stream:
            arch_conf = yaml.safe_load(stream)["arch"]
            self.width = arch_conf["width"]
            self.radius = arch_conf["radius"]
            self.height = arch_conf["height"]

    def getParameters(self):
        return self.adaptableParametersDict

    def updateParams(self, af=None):
        self.time += .01*self.vitesse

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def render(self, textures, af=None):
        self.bindUniform(af)
        self.updateParams(af)
        textures[0].use(1)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]

@register_node(OP_CODE_MASKARCHE)
class MaskArcheNode(ShaderNode, Utils):
    op_title = "MaskArche"
    op_code = OP_CODE_MASKARCHE
    content_label = ""
    content_label_objname = "shader_maskarche"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = MaskArche(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()


    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
