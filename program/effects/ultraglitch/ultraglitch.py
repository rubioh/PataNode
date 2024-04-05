import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Effects
from node.node_conf import register_node


OP_CODE_UGLITCH = name_to_opcode('ultraglitch')

@register_program(OP_CODE_UGLITCH)
class UltraGlitch(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "UltraGlitch"

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
        frag_path = join(dirname(__file__), "ultraglitch.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 1
        self.seed = 0
        self.stop = 0
        self.tstop = 0
        self.freq = 1
        self.time = 0
        self.go_strobe = True

    def initUniformsBinding(self):
        binding = {
            'iResolution' : 'win_size',
            'iTime' : 'time',
            'iChannel0' : 'iChannel0',
            'on_chill' : 'go_strobe',
            'change_seed' : 'seed',
            'stop' : 'tstop'
        }
        super().initUniformsBinding(binding, program_name='')
        self.addProtectedUniforms(['iChannel0'])

    def updateParams(self, af):
        if af is None:
            return
        self.time = af['time']
        if af["on_kick"]:
            self.seed = np.random.randint(0, 1000)
            self.stop += 1

        if self.go_strobe:
            self.freq = 10
        else:
            self.freq = 1
        if not af["on_chill"] and self.stop < 16:
            self.go_strobe = True
        else:
            self.go_strobe = False
        self.tstop = self.stop>16
        self.tstop = 0

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        textures[0].use(1)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_UGLITCH)
class UGlitchNode(ShaderNode, Effects):
    op_title = "UltraGlitch"
    op_code = OP_CODE_UGLITCH
    content_label = ""
    content_label_objname = "shader_ultraglitch"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = UltraGlitch(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
