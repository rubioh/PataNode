import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Scene
from node.node_conf import register_node
import moderngl as mgl
from matplotlib.colors import rgb_to_hsv, hsv_to_rgb


OP_CODE_TRUCHET = name_to_opcode('truchet')

@register_program(OP_CODE_TRUCHET)
class Truchet(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Truchet"
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 4
        fbos_specification = [
            [(80,80), 4, 'f4'],
            [(80,80), 4, 'f4'],
            [(1980,1980), 4, 'f4'],
            [self.win_size, 4, 'f4']
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "connex/connex.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="connex_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "draw/draw.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="draw_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "truchet.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.program["angle_rot"] = 0.0
        self.program["deep"] = 0.0
        self.toc = np.float32([0.01])
        self.angle_rot = 0
        self.smooth_fast = 0
        self.color = np.array([1.0, 0.58, 0.29])
        self.deep_tic = 0.05
        self.deep = 0
        self.iFrame = 0
        self.bwin_size = (80, 80)
        self.twin_size = (1980, 1980)
        self.K = 0
        self.K_final = 0
        self.accum_rot = 0
        self.nrj_slow = 0
        self.smooth_low_final = 0
        self.time = 0

        self.TruchetSampler = 1
        self.iChannel0 = 2
        self.iChannel1 = 3

    def initUniformsBinding(self):
        binding = {
                'iFrame': 'iFrame',
                'TruchetSampler' : 'TruchetSampler',
                'iResolution': 'bwin_size'
                }
        super().initUniformsBinding(binding, program_name='connex_')
        binding = {
                'iResolution': 'twin_size',
                'iChannel0' : 'iChannel0',
        }
        super().initUniformsBinding(binding, program_name='draw_')
        binding = {
                'iTime': 'iTime',
                'iResolution': 'win_size',
                'iChannel1' : 'iChannel1',
                'energy_fast' : 'smooth_fast',
                'energy_slow' : 'nrj_slow',
                'angle_rot' : 'angle_rot',
                'deep' : 'deep',
                'K' : 'K_final',
                'smooth_low': 'smooth_low_final',
                'accum_rot' : 'accum_rot',
                'iTime' : 'time'
        }
        super().initUniformsBinding(binding, program_name='')
        super().addProtectedUniforms(
                ['TruchetSampler', 'iChannel0', 'iChannel1']
        )

    def updateParams(self, fa):
        if fa is None:
            return
        self.smooth_low_final = fa["smooth_low"] ** 2.0 * 3.0 + fa["on_chill"] * 2.0 + 0.1
        self.time = fa['time']
        self.smooth_fast = self.smooth_fast * 0.2 + 0.8 * fa["low"][3] * .5
        self.nrj_slow = fa["full"][1] * .5

        tmp = rgb_to_hsv(self.color)
        tmp[0] += 0.002
        tmp[0] = tmp[0] % 1
        self.color = hsv_to_rgb(tmp)

        if fa["on_chill"]:
            self.deep_tic += 0.001
        else:
            self.deep_tic -= 0.005
        self.deep_tic = np.clip(self.deep_tic, 0.1, 0.3)
        self.angle_rot += self.toc + 0.001

        self.deep += (
            self.deep_tic
            - self.smooth_fast / 4.0 * (0.5 + 0.25 * np.cos(fa["time"] / 16.0))
        ) * 0.3
        self.deep = (self.deep - 512 * np.pi) % (1024 * np.pi) + 512 * np.pi

        if fa["on_snare"]:
            self.K += 1

        if self.K % 32 == 0.0 and not fa["on_chill"]:
            self.iFrame = 0
        if fa["on_chill"] and self.iFrame > 400:
            self.iFrame = 0
        self.iFrame += 1

        self.accum_rot += fa["smooth_low"]
        self.K_final = self.K // 16.0 if self.K % 64 < 16 else self.K

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='connex_')
        self.programs_uniforms.bindUniformToProgram(af, program_name='draw_')
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def render(self, af):
        self.bindUniform(af)
        self.updateParams(af)

        if self.iFrame % 3 == 0:
            self.fbos[0].color_attachments[0].filter == (mgl.NEAREST, mgl.NEAREST)
            self.fbos[1].color_attachments[0].filter == (mgl.NEAREST, mgl.NEAREST)
            self.fbos[1].clear()
            self.fbos[1].use()
            self.fbos[0].color_attachments[0].use(1)
            self.connex_vao.render()
            self.fbos[0], self.fbos[1] = self.fbos[1], self.fbos[0]

        self.fbos[0].color_attachments[0].use(3)
        self.fbos[3].use()
        self.vao.render()
        return self.fbos[3].color_attachments[0]

    def norender(self):
        return self.fbos[3].color_attachments[0]


@register_node(OP_CODE_TRUCHET)
class TruchetNode(ShaderNode, Scene):
    op_title = "Truchet"
    op_code = OP_CODE_TRUCHET
    content_label = ""
    content_label_objname = "shader_truchet"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Truchet(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)
        return output_texture
