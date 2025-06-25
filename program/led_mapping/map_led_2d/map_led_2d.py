import time
from os.path import dirname, basename, isfile, join

import numpy as np
import moderngl as mgl

from program.program_conf import (
    SQUARE_VERT_PATH,
    get_square_vertex_data,
    register_program,
    name_to_opcode,
)
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, LED
from node.node_conf import register_node


OP_CODE_MAPLED2D = name_to_opcode("map_led_2d")


@register_program(OP_CODE_MAPLED2D)
class MapLed2D(ProgramBase):
    def __init__(
        self,
        ctx=None,
        major_version=3,
        minor_version=3,
        win_size=(1920, 1080),
        light_engine=None,
    ):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Map Led 2D"
        self.light_engine = light_engine

        self.initParams()
        self.initVBOs()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initPixels()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [[self.win_size, 4, "f4"]]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        ### Vertex To LED
        vert_path = join(dirname(__file__), "pixel/get_pixel_col.vert")
        frag_path = None
        varyings = ["out_col"]
        vao_binding = [(self.vbo1, "2f4", "in_pos")]
        self.loadProgramToCtx(
            vert_path,
            frag_path,
            reload,
            name="get_pixel_col_",
            vao_binding=vao_binding,
            varyings=varyings,
        )

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "view_led.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="view_led_")

    def initVBOs(self):
        self.vbo1 = self.ctx.buffer(reserve=self.N_part_max * 8)
        self.vbo2 = self.ctx.buffer(reserve=self.N_part_max * 16)

    def initParams(self):
        self.N_part_max = 1000
        self.N_part = 0
        self.iChannel0 = 1
        self.LightsBuffer = 12
        self.input_texture = 3
        self.buf_col = np.zeros((self.N_part_max, 3))

    def initPixels(self):
        self.shader_light_mapper = self.light_engine.shader_mapper
        self.shader_light_mapper.bind_position_in_vbo(self.vbo1)

        byte_array = self.shader_light_mapper.pixels_positions.tobytes()
        self.pos_texture = self.ctx.texture(
            (self.N_part_max, 1),
            components=2,
            data=byte_array,
            dtype="f4",
        )

    def initUniformsBinding(self):
        binding = {"iChannel0": self.iChannel0}
        super().initUniformsBinding(binding, program_name="get_pixel_col_")
        binding = {
            "iResolution": self.win_size,
            "input_texture": self.input_texture,
            "LightsBuffer": self.LightsBuffer,
        }
        super().initUniformsBinding(binding, program_name="view_led_")
        self.addProtectedUniforms(["iChannel0", "input_texture", "LightsBuffer"])

    def bindUniform(self, af):
        super().bindUniform(af)

    def render(self, texture, af=None):
        self.bindUniform(af)
        # PREVIS SHOW
        # texture[0].use(3)
        # self.pos_texture.use(12)
        # self.fbos[0].use()
        # self.view_led_vao.render()
        # WRITE COLOR
        texture[0].use(1)
        self.get_pixel_col_vao.transform(self.vbo2, mgl.POINTS, self.N_part_max)
        self.shader_light_mapper.read_color(self.vbo2)
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_MAPLED2D)
class MapLed2DNode(ShaderNode, LED):
    op_title = "Map Led 2D"
    op_code = OP_CODE_MAPLED2D
    content_label = ""
    content_label_objname = "shader_map_led_2d"

    def __init__(self, scene, light_engine):
        super().__init__(scene, inputs=[1], outputs=[1])
        self.program = MapLed2D(ctx=self.scene.ctx, light_engine=scene.app.light_engine)
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            return self.program.norender()
        input_nodes = self.getShaderInputs()
        if len(input_nodes) == 0:
            return self.program.norender()
        if len(input_nodes) == 1:
            texture = input_nodes[0].render(audio_features)
        if texture is None:
            return self.program.norender()
        out_texture = self.program.render([texture], audio_features)
        # return out_texture
        return texture
