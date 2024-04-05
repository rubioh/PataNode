import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Utils
from node.node_conf import register_node

OP_CODE_CURLNOISE = name_to_opcode('curlnoise')

class CurlNoise(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "CurlNoise"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 3
        fbos_specification = [
            [self.win_size, 4, 'f4'],
            [self.win_size, 4, 'f4'],
            [self.win_size, 4, 'f4'],
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        # program
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "curlnoise.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

        # ink_program
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Ink/ink.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name='ink_')

    def initUniformsBinding(self):
        binding = {
            'UVState' : 'UVState',
            'a' : 'advection_level',
            'dt' : 'dt',
            'iResolution' : 'win_size',
            'scale' : 'scale_final',
            'iFrame' : 'iFrame',
            'iTime' : 'time_final',
            'energy' : 'energy'
        }
        super().initUniformsBinding(binding, program_name='ink_')
        binding = {
            'UVState' : 'UVState2',
            'iChannel0' : 'iChannel0'
        }
        super().initUniformsBinding(binding, program_name='')
        self.addProtectedUniforms(['iChannel0', 'UVState'])

    def initParams(self):
        self.UVState = 1
        self.UVState2 = 2
        self.iChannel0 = 3
        self.time_final = 0
        self.scale_final = 0

        self.seed = np.random.rand(*self.win_size, 2)
        self.seed_tex = self.ctx.texture(self.win_size, components=4, dtype="f4")
        self.seed_tex.write(self.seed)
        self.vort_amount = 1.5
        self.dt = 0.1
        self.advection_level = 1
        self.scale = 1
        self.iFrame = -1
        self.wait = 0
        self.wait2 = 0
        self.on_kick = 0
        self.energy = 0
        self.time = 0


    def updateParams(self, af):
        if af is None:
            return
        self.on_kick = af['on_kick']
        self.time = af['time']
        self.iFrame += 1
        self.energy = af['smooth_full']*.5 + af['smooth_low']*.5
        self.time_final = self.time * .1
        self.scale_final = self.scale ** 3

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='ink_')
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def render(self, textures, af=None):
        self.bindUniform(af)
        self.updateParams(af)

        # Ink Texture
        self.fbos[0], self.fbos[1] = self.fbos[1], self.fbos[0]
        self.fbos[0].color_attachments[0].use(1)
        self.fbos[1].use()
        self.ink_vao.render()

        self.fbos[1].color_attachments[0].use(2)
        textures[0].use(3)
        self.fbos[2].use()
        self.vao.render()
        return self.fbos[2].color_attachments[0]

    def norender(self):
        return self.fbos[2].color_attachments[0]


@register_node(OP_CODE_CURLNOISE)
class CurlNoiseNode(ShaderNode, Utils):
    op_title = "CurlNoise"
    op_code = OP_CODE_CURLNOISE
    content_label = ""
    content_label_objname = "shader_curlnoise"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = CurlNoise(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
