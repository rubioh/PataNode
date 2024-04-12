import time
import numpy as np
import PIL
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Scene
from node.node_conf import register_node
from nodeeditor.utils import dumpException

OP_CODE_GSSTYLIZED = name_to_opcode('gsstylized')

@register_program(OP_CODE_GSSTYLIZED)
class GSStylized(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "GS Stylized"
        self.initParams()
        self.initFBOSpecifications()
        self.initProgram()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        self.required_fbos = 4
        fbos_specification = [
            [self.bwin_size, 4, 'f4'],
            [self.bwin_size, 4, 'f4'],
            [self.win_size, 4, 'f4'],
            [self.bwin_size, 4, 'f4'],
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        # ReacDif PROGRAM
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "ReacDifShader/ReacDif.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="reacdif_")
        # Init PROGRAM
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "InitShader/frag.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="init_")
        # Program
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "gsstylized.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    
    def initUniformsBinding(self):
        binding = {
            'iResolution' : 'bwin_size',
            'iChannel0' : 'iChannel0',
            'f' : 'f_current',
            'k' : 'k_current',
            'Db' : 'Db',
            'Da' : 'Da',
            'on_kick' : 'on_kick',
            'radius_triangle' : 'radius_triangle'
        }
        super().initUniformsBinding(binding, program_name='reacdif_')
        binding = {
            'iResolution' : 'win_size',
            'iChannel0' : 'iChannel1',
            'K' : 'K',
            'energy': 'smooth_fast',
            'mode_flick': 'mode_flick',
            'dkick' : 'dkick'
        }
        super().initUniformsBinding(binding, program_name='')
        self.addProtectedUniforms(['iChannel0', 'iChannel1'])

    def load_data(self):
        img = PIL.Image.open("./data/patat_hd.png")
        data = np.asarray(img)
        data = data[:, :, 0].T.copy()
        data = data.reshape(*data.shape, 1)
        self.patat_texture = self.ctx.texture(self.bwin_size, components=1, dtype="f1")

    def get_init_texture(self):
        self.init_program["iResolution"] = np.array(self.bwin_size)
        self.init_program["mode"] = self.init_mode

        # self.patat_texture.use(2)
        self.fbos[3].clear()
        self.fbos[3].use()
        self.init_vao.render()

        tmp = self.fbos[3].color_attachments[0]
        self.fbos[0].color_attachments[0].write(tmp.read())
        self.fbos[1].color_attachments[0].write(tmp.read())

    def init_texture4(self):
        init_array = np.float32(np.ones((self.bwin_size[1], self.bwin_size[0], 4)) * 0)
        init_array[:, :, 0] = 180 / 255
        s = self.bwin_size[1] // 2
        i = 50
        e = self.bwin_size[0] // 2
        init_array[s - i : s + i, e - i : e + i, 1] = 1
        init_array[:, :, 2] = 0
        self.fbos[0].color_attachments[0].write(init_array)
        self.fbos[1].color_attachments[0].write(init_array)

    def initParams(self):
        self.iChannel0 = 0
        self.iChannel1 = 1
        self.bwin_size = (800, 450)
        self.iFrame = 0
        self.fk = np.array([0.041, 0.061])
        self.Da = 0.21
        self.Db = 0.105
        self.n_iter = 8

        self.radius = 0.1
        self.on_kick = 0.0
        self.center = np.float32([0.0, 0.0])

        self.preset = np.array(
            [
                (0.037, 0.06),
                (0.03, 0.062),
                (0.025, 0.062),
                (0.029, 0.057),
                (0.026, 0.051),
                (0.034, 0.056),
                (0.014, 0.054),
                (0.014, 0.045),
            ]
        )

        self.slow_preset = np.array([0.026, 0.051])

        self.render_preset = np.copy(self.slow_preset)
        self.preset_idx = 0
        self.change = 0
        self.change_init = 0
        self.initialize = False
        self.center = np.zeros(2)
        self.on_chill = 0.0
        self.radius_triangle = 1.0
        self.K = 0
        self.sens = 1
        self.smooth_fast = 0
        self.init_mode = 0
        self.mode_flick = 1
        self.go_flick = 0.0
        self.sensflick = -1.0
        self.dkick = 0
        self.loaded = False
        self.f_current = self.render_preset[0]
        self.k_current = self.render_preset[1]

    def updateParams(self, af):
        if self.fbos[0] is not None and self.loaded is False:
            self.load_data()
            self.init_texture4()
            self.loaded = True
        if af is None:
            return
        self.dkick = (1.0 - af["decaying_kick"]) ** 1.0 / 4.0
        if self.on_chill == 1 and af["mini_chill"] == 0:
            self.on_chill = 0
            self.change = 4
            self.change_triangle = 8
            self.initialize = True
            self.get_init_texture()

        if af["on_chill"]:
            self.K += 0.01 * self.sens
            if self.K > 1:
                self.K = 1
                self.sens = -1
            if self.K < 0:
                self.K = 0
                self.sens = 1

        else:
            self.K = np.round(self.K)

        self.smooth_fast = self.smooth_fast * 0.2 + 0.8 * af["full"][0]
        self.n_iter = int(np.clip((self.smooth_fast * 10.0), 1, 17))

        if af["on_kick"]:
            self.on_kick = 1
            self.change += 1
            self.change_init += 1
            self.radius_triangle -= 0.05
            self.go_flick += 1
            if self.change > 4:
                self.preset_idx = np.random.randint(0, len(self.preset))
                if (self.preset_idx == 2):
                    self.preset_idx += 1
                self.change = 0
            if self.change_init >= 32:
                self.change_init %= 32
                self.get_init_texture()
                self.radius_triangle = 1
                self.init_mode += 1
                self.init_mode %= 4
            if self.go_flick >= 128:
                self.go_flick = 0
                self.mode_flick ^= 1

            self.center[0] = np.random.rand() - 0.5
            self.center[1] = (np.random.rand() - 0.5) * 9 / 16

        else:
            self.on_kick = 0

        if af["mini_chill"]:
            self.render_preset = self.slow_preset
            self.on_chill = 1
        else:
            self.render_preset = self.preset[self.preset_idx]

        diff = self.render_preset - self.fk
        self.fk = self.fk + diff * 3e-2

        self.f_current = self.render_preset[0]
        self.k_current = self.render_preset[1]


    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='reacdif_')
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)

        for i in range(self.n_iter):
            self.fbos[0], self.fbos[1] = self.fbos[1], self.fbos[0]
            self.fbos[1].color_attachments[0].use(0)
            self.fbos[0].clear()
            self.fbos[0].use()
            self.reacdif_vao.render()

        self.fbos[0].color_attachments[0].use(1)
        self.fbos[2].use()
        self.vao.render()
        return self.fbos[2].color_attachments[0]

    def norender(self):
        return self.fbos[2].color_attachments[0]


@register_node(OP_CODE_GSSTYLIZED)
class GSStylizedNode(ShaderNode, Scene):
    op_title = "GSStylized"
    op_code = OP_CODE_GSSTYLIZED
    content_label = ""
    content_label_objname = "shader_gs_stylized"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = GSStylized(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()
        return self.program.render(audio_features)
