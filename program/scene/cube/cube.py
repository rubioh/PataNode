import time
import numpy as np
from matplotlib.colors import rgb_to_hsv, hsv_to_rgb
from os.path import dirname, basename, isfile, join

from program.program_conf import (
    SQUARE_VERT_PATH,
    get_square_vertex_data,
    register_program,
    name_to_opcode,
)
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Scene
from node.node_conf import register_node


OP_CODE_CUBE = name_to_opcode("cube")


@register_program(OP_CODE_CUBE)
class Cube(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Cube"

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
        frag_path = join(dirname(__file__), "cube.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initUniformsBinding(self):
        binding = {
            "iTime": "time",
            "iResolution": "win_size",
            "energy_fast": "smooth_fast_final",
            "energy_mid": "emid",
            "color": "color_final",
            "go_rot": "go_rot",
            "face": "face",
            "deep": "deep_tic_final",
            "side_col": "side_col",
            "N_sq": "N_sq",
            "zoom_factor": "zoom_factor",
            "show_bulb": "show_bulb",
        }
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def initParams(self):
        self.program["go_rot"] = 0.0
        self.program["deep"] = 0.0
        self.smooth_fast = 1
        self.smooth_mid = 1
        self.smooth_tmp = 1
        self.color = np.array([1.0, 0.58, 0.29])
        self.deep_tic = 0.05
        self.go_rot = 0.0
        self.face = 1.0
        self.time = 0
        self.smooth_fast_final = 0
        self.emid = 0
        self.color_final = self.color
        self.deep_tic_final = 0
        self.side_col = 1
        self.N_sq = 1
        self.zoom_factor = 1.0
        self.show_bulb = 1

    def updateParams(self, fa=None):
        if fa is None:
            return
        self.time = fa["time"] / 2 * 0.25
        self.smooth_fast_final = (
            np.log(self.smooth_tmp + 1.0) * fa["bpm"] / 75 + self.deep_tic
        )
        self.emid = (fa["low"][2] + self.smooth_fast / 2) * 0.5
        tmp = rgb_to_hsv(self.color)
        tmp[0] += 0.002
        tmp[0] = tmp[0] % 1
        self.color = hsv_to_rgb(tmp)
        self.color_final = self.color * 0.7

        self.smooth_fast = self.smooth_fast * 0.2 + 0.8 * fa["low"][3]
        self.smooth_mid = self.smooth_mid * 0.2 + 0.8 * fa["low"][2]
        tmp = max(self.smooth_fast - self.smooth_mid * 0.95, 0) * 3
        self.smooth_tmp = 0.5 * self.smooth_tmp + 0.5 * tmp

        if fa["on_chill"]:
            self.deep_tic += 0.01
        else:
            self.deep_tic -= 0.2
        self.deep_tic = np.clip(self.deep_tic, 0.0, 2.0)

        if fa["on_kick"]:
            self.go_rot += np.pi / 2.0 * 0.08
            self.face = np.random.randint(1, 4) * (-1) ** np.random.randint(1, 3)

        self.go_rot = np.pi / 2 * (1.0 - (fa["decaying_kick"]))
        self.deep_tic_final = self.deep_tic * 2.0

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


@register_node(OP_CODE_CUBE)
class CubeNode(ShaderNode, Scene):
    op_title = "Cube"
    op_code = OP_CODE_CUBE
    content_label = ""
    content_label_objname = "shader_cube"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Cube(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)
        return output_texture
