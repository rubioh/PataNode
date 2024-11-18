import time
from PIL import Image
import moderngl
import numpy as np
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


OP_CODE_TEXTURE = name_to_opcode("texture")


@register_program(OP_CODE_TEXTURE)
class Texture(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "texture"
        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [[self.win_size, 4, "f4"]]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "texture.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.path = "./assets/textures/lichen.jpg"
        self.reload_texture(self.path)

    def reload_texture(self, v):
        self.path = v
        jpg_image = Image.open(v)
        bmp_image = jpg_image.convert("RGB")
        b = list(bmp_image.getdata())
        b2 = []
        for x in b:
            for data in x:
                b2.append(data)
        b = bytes(b2)
        self.texture = self.ctx.texture(
            (1024, 1024), components=3, dtype="f1", data=b
        )
        self.texture.repeat_x = True
        self.texture.repeat_y = True

    def initUniformsBinding(self):
        binding = {
        }
        self.add_text_edit_cpu_adaptable_parameter("text_path", self.path, self.reload_texture)
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def updateParams(self, af=None):
        v = self.getCpuAdaptableParameters()["program"]["text_path"]["eval_function"]["value"]
        if self.path != v:
            self.path = v
            self.reload_texture(v)

    def norender(self):
        return self.fbos[0].color_attachments[0]

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.program["iChannel0"] = 0
        self.texture.use(0)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

@register_node(OP_CODE_TEXTURE)
class TextureNode(ShaderNode, Scene):
    op_title = "texture"
    op_code = OP_CODE_TEXTURE
    content_label = ""
    content_label_objname = "shader_texture"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Texture(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)
        return output_texture
