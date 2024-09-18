import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import (
    SQUARE_VERT_PATH,
    get_square_vertex_data,
    register_program,
    name_to_opcode,
)
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Effects
from node.node_conf import register_node


OP_CODE_CREPET = name_to_opcode("crepet")


@register_program(OP_CODE_CREPET)
class CRepet(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "CRepet"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, "f4"],
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "column_repetition.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 1
        self.start_ux = 800
        self.size = 0
        self.mode_size = 1
        self.offset_y = 0
        self.seed = np.random.rand() * 2.0 * 3.14159

    def initUniformsBinding(self):
        binding = {
            "iChannel0": "iChannel0",
            "size": "size",
            "start_ux": "start_ux",
            "offset_y": "offset_y",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def updateParams(self, af=None):
        if af is None:
            return

        self.start_ux = (
            self.win_size[0] // 2
            + np.sin(
                af["on_tempo32"] * 2.0 * 3.14159 + af["smooth_low"] * 2.0 + self.seed
            )
            * self.win_size[1]
            // 4
        )
        self.size = (
            (af["low"][2] ** 4 * 3.0 + af["smooth_low"] * 2.0)
            * 100.0
            * (0.5 + 0.5 * np.cos(af["time"] * 0.05 + self.seed))
        )

        self.offset_y = (
            100.0
            * (af["smooth_low"] ** 0.5 * 5.0)
            * np.sin(af["on_tempo2"] * 2.0 * 3.14159 + self.seed)
        )

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        textures[0].use(1)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_CREPET)
class CRepetNode(ShaderNode, Effects):
    op_title = "CRepet"
    op_code = OP_CODE_CREPET
    content_label = ""
    content_label_objname = "shader_crepet"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = CRepet(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
