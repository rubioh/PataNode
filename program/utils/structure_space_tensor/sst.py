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

from node.shader_node_base import ShaderNode, Utils
from node.node_conf import register_node


OP_CODE_SST = name_to_opcode("structured space tensor")


class SST(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        """
        Structure Space Tensor
        Information about the orientation of the edge on a given image
        This return the principal eigenvector and its corresponding eigenvalue
        """
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Structured Space Tensor"

        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        self.required_fbos = 3
        fbos_specification = [[self.win_size, 4, "f4"] for i in range(3)]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "SST/rgb2lab.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="rgb2lab_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "SST/sst.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="sst_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "SST/vblur.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="vblur_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "SST/hblur.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="hblur_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "SST.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.sigmaC = 3.0
        self.iChannel0 = 0

    def initUniformsBinding(self):
        binding = {"iChannel0": "iChannel0", "iResolution": "win_size"}
        super().initUniformsBinding(binding, program_name="rgb2lab_")
        binding = {"iChannel0": "iChannel0", "iResolution": "win_size"}
        super().initUniformsBinding(binding, program_name="sst_")
        binding = {
            "sigmaC": "sigmaC",
            "iChannel0": "iChannel0",
        }
        super().initUniformsBinding(binding, program_name="vblur_")
        binding = {
            "sigmaC": "sigmaC",
            "iChannel0": "iChannel0",
        }
        super().initUniformsBinding(binding, program_name="hblur_")
        binding = {"iChannel0": "iChannel0", "iResolution": "win_size"}
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="rgb2lab_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="sst_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="vblur_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="hblur_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.bindUniform(af)

        texture = textures[0]

        # RGB to LAB
        texture.use(0)
        texture.repeat_x = False
        texture.repeat_y = False
        self.fbos[0].use()
        self.rgb2lab_vao.render()

        # Compute SST
        self.fbos[0].color_attachments[0].use(0)
        self.fbos[1].use()
        self.sst_vao.render()

        ### BLUR SST
        self.fbos[1].color_attachments[0].use(0)
        self.fbos[0].use()
        self.vblur_vao.render()

        self.fbos[0].color_attachments[0].repeat_x = False
        self.fbos[0].color_attachments[0].repeat_y = False
        self.fbos[0].color_attachments[0].use(0)
        self.fbos[1].use()
        self.hblur_vao.render()

        self.fbos[1].color_attachments[0].use(0)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_SST)
class SSTNode(ShaderNode, Utils):
    op_title = "SST"
    op_code = OP_CODE_SST
    content_label = ""
    content_label_objname = "shader_sst"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = SST(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
