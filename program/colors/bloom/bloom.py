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

from node.shader_node_base import ShaderNode, Colors
from node.node_conf import register_node

OP_CODE_BLOOM = name_to_opcode("bloom")


class Bloom(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Bloom"

        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        level = self.level
        self.required_fbos = level * 2 + 1
        fbos_specification = [[self.win_size, 4, "f4"]]
        fbos_specification += [[self.resolution[i], 4, "f4"] for i in range(level)] + [
            [self.resolution[i], 4, "f4"] for i in range(level)
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "bloom.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Blur/vblur.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="vblur_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Blur/hblur.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="hblur_")

    def initParams(self):
        self.level = 8
        self.resolution = [
            (self.win_size[0] // (2 ** (i + 1)), self.win_size[1] // (2 ** (i + 1)))
            for i in range(self.level)
        ]

        self.compression = 3.72
        self.bloom_rate = 1.0

        self.ViChannel0 = 10
        self.HPrev = 11

        self.HiChannel0 = 12

        self.iChannel0 = 10
        self.Bloom = 1

    def initUniformsBinding(self):
        binding = {"iChannel0": "ViChannel0", "Prev": "HPrev"}
        super().initUniformsBinding(binding, program_name="vblur_")
        binding = {
            "iChannel0": "HiChannel0",
        }
        super().initUniformsBinding(binding, program_name="hblur_")
        binding = {
            "iChannel0": "iChannel0",
            "Bloom": "Bloom",
            "iResolution": "win_size",
            "compression": "compression",
            "bloom_rate": "bloom_rate",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0", "Prev", "Bloom"])

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="vblur_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="hblur_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.bindUniform(af)

        texture = textures[0]
        level = self.level

        texture.use(10)
        texture.repeat_x = False
        texture.repeat_y = False
        self.vblur_program["level"] = -1
        self.vblur_program["iResolution"] = self.resolution[-1]
        self.fbos[-1].use()
        self.vblur_vao.render()

        self.fbos[-1].color_attachments[0].repeat_x = False
        self.fbos[-1].color_attachments[0].repeat_y = False
        self.hblur_program["iResolution"] = self.resolution[-1]
        self.fbos[-1].color_attachments[0].use(12)
        self.fbos[-1 - level].use()
        self.hblur_vao.render()

        for i in range(2, level + 1):
            texture.use(85)
            self.fbos[-i - level + 1].color_attachments[0].repeat_x = False
            self.fbos[-i - level + 1].color_attachments[0].repeat_y = False
            self.fbos[-i - level + 1].color_attachments[0].use(11)
            self.vblur_program["level"] = -i
            self.vblur_program["iResolution"] = self.resolution[-i]
            self.fbos[-i].use()
            self.vblur_vao.render()

            self.hblur_program["iResolution"] = self.resolution[-i]
            self.fbos[-i].color_attachments[0].use(12)
            self.fbos[-i - level].color_attachments[0].repeat_x = False
            self.fbos[-i - level].color_attachments[0].repeat_y = False
            self.fbos[-i - level].use()
            self.hblur_vao.render()

        texture.use(10)
        self.fbos[1].color_attachments[0].use(1)
        self.fbos[0].clear()
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_BLOOM)
class BloomNode(ShaderNode, Colors):
    op_title = "Bloom"
    op_code = OP_CODE_BLOOM
    content_label = ""
    content_label_objname = "shader_bloom"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = Bloom(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
