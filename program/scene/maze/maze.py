import time

import numpy as np

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_MAZE = name_to_opcode("MAZE")


@register_program(OP_CODE_MAZE)
class Maze(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Maze"

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
        frag_path = join(dirname(__file__), "maze.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.vitesse = 0.4
        self.offset = 0
        self.intensity = 5
        self.smooth_fast = 0
        self.time = 0
        self.tf = 0
        self.eslow = 0.4
        self.emid = 0.2

        self.smooth_fast_final = self.smooth_fast / 2.0
        self.scale_final = 16 + 8 * np.cos(time.time() * 0.1)

    def initUniformsBinding(self):
        binding = {
            "iTime": "time",
            "energy_fast": "smooth_fast_final",
            "energy_slow": "eslow",
            "energy_mid": "emid",
            "tf": "tf",
            "intensity": "intensity",
            "scale": "scale_final",
        }
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def updateParams(self, af=None):
        self.vitesse = np.clip(self.vitesse, 0, 2)
        self.intensity = np.clip(self.intensity, 2, 10)
        self.time += 1 / 60 * (1 + self.vitesse)
        self.tf += 0.01

        if af is None:
            return

        self.smooth_fast = self.smooth_fast * 0.2 + 0.8 * af["full"][3]

        if af["full"][1] < 1.0 or af["full"][2] < 0.7:
            self.vitesse += 0.01
            self.intensity += 0.05

            if self.time > 500 and self.vitesse > 1.5:
                self.time = 0
                self.tf = 0
        else:
            self.vitesse -= 0.04
            self.intensity -= 0.1

        self.vitesse = np.clip(self.vitesse, 0, 2)
        self.intensity = np.clip(self.intensity, 2, 10)
        self.time += 1 / 60 * (1 + self.vitesse)
        self.tf += 0.01
        self.eslow = af["full"][1] * 0.75
        self.emid = af["low"][2] / 2.0

        self.smooth_fast_final = self.smooth_fast / 2.0
        self.scale_final = 16 + 8 * np.cos(time.time() * 0.1)

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


@register_node(OP_CODE_MAZE)
class MazeNode(ShaderNode, Scene):
    op_title = "Maze"
    op_code = OP_CODE_MAZE
    content_label = ""
    content_label_objname = "shader_maze"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Maze(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)

        return output_texture
