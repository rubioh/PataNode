import time
import numpy as np
import cv2
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


OP_CODE_ORIENTATIONAA = name_to_opcode("orientationAA")


class OrientationAA(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Orientation Anti Aliasing"

        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        rfbos = 3
        self.required_fbos = rfbos
        fbos_specification = [[self.win_size, 4, "f4"] for i in range(rfbos)]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "memory.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="memory_")
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "orientationaa.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.sigmaC = 0.5
        self.sigmaA = 5.0
        self.BaseTex = 0
        self.SST = 1
        self.previous_SST = 2
        self.mix_rate = 0.5

    def updateParams(self, fa):
        pass

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "SST": "SST",
            "previous_SST": "previous_SST",
            "mix_rate": "mix_rate",
        }
        super().initUniformsBinding(binding, program_name="memory_")
        binding = {
            "iResolution": "win_size",
            "BaseTex": "BaseTex",
            "SST": "SST",
            "sigmaA": "sigmaA",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["SST", "BaseTex", "previous_SST"])

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="memory_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None, SST=None):
        self.updateParams(af)
        self.bindUniform(af)

        basetex = textures[0]
        SST = textures[1]

        SST.use(1)
        self.fbos[1].color_attachments[0].use(2)
        self.fbos[0].use()
        self.memory_vao.render()
        self.fbos[0], self.fbos[1] = self.fbos[1], self.fbos[0]

        basetex.use(0)
        self.fbos[1].color_attachments[0].use(1)
        self.fbos[2].use()
        self.vao.render()
        return self.fbos[2].color_attachments[0]

    def norender(self):
        return self.fbos[2].color_attachments[0]


@register_node(OP_CODE_ORIENTATIONAA)
class OrientationAANode(ShaderNode, Effects):
    op_title = "Orientation Anti-Aliasing"
    op_code = OP_CODE_ORIENTATIONAA
    content_label = ""
    content_label_objname = "shader_orientation_aa"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1, 2], outputs=[3])
        self.program = OrientationAA(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()
        input_nodes = self.getShaderInputs()
        if len(input_nodes) < 2:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        sst = input_nodes[1].render(audio_features)
        if texture is None or sst is None:
            return self.program.norender()
        output_texture = self.program.render([texture, sst], audio_features)
        return output_texture
