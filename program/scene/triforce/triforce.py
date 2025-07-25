from os.path import dirname, join
import random
from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode
import glm
import keyboard

OP_CODE_TRIFORCE = name_to_opcode("Triforce")
RED = glm.vec3(1.0, 0.0, 0.0)
PURPLE = glm.vec3(1.0, 0.0, 1.0)
CYAN = glm.vec3(0.0, 1.0, 1.0)
BLUE = glm.vec3(0.0, 0.0, 1.0)
WHITE = glm.vec3(1.0, 1.0, 1.0)
BLACK = glm.vec3(0.2, 0.2, 0.2)

PAL1 = glm.vec3(24.0 / 255.0, 1.0 / 255.0, 97.0 / 255.0)
PAL2 = glm.vec3(79.0 / 255.0, 23.0 / 255.0, 135.0 / 255.0)
PAL3 = glm.vec3(235.0 / 255.0, 54.0 / 255.0, 120.0 / 255.0)
PAL4 = glm.vec3(251.0 / 255.0, 119.0 / 255.0, 60.0 / 255.0)

COLOR = [PAL1, PAL2, PAL3, PAL4]
COLOR2 = [
    glm.vec3(228.0 / 255.0, 3.0 / 255.0, 3.0 / 255.0),
    glm.vec3(255.0 / 255.0, 140.0 / 255.0, 0.0 / 255.0),
    glm.vec3(255.0 / 255.0, 237.0 / 255.0, 0.0 / 255.0),
    glm.vec3(0.0 / 255.0, 128.0 / 255.0, 38.0 / 255.0),
    glm.vec3(0.0 / 255.0, 76.0 / 255.0, 255.0 / 255.0),
    glm.vec3(115.0 / 255.0, 41.0 / 255.0, 130.0 / 255.0),
]


@register_program(OP_CODE_TRIFORCE)
class Triforce(ProgramBase):
    def __init__(
        self,
        ctx=None,
        major_version=3,
        minor_version=3,
        win_size=(960, 540),
        light_engine=None,
    ):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Triforce"
        self.light_engine = light_engine
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
        frag_path = join(dirname(__file__), "Triforce.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def get_col(self):
        return COLOR

    def get_col2(self):
        return COLOR

    def apply_cols(self):
        self.d11 = self.colors[0]
        self.d12 = self.colors[1]
        self.d13 = self.colors[2]
        self.d21 = self.colors[3]
        self.d22 = self.colors[4]
        self.d23 = self.colors[5]
        self.d31 = self.colors[6]
        self.d32 = self.colors[7]
        self.d33 = self.colors[8]

    def initParams(self):
        keyboard.on_press_key("n", self.upp)
        keyboard.on_press_key("p", self.down)
        self.wo = 0
        self.colors = [
            glm.vec3(0.0, 0.0, 0.0),
            glm.vec3(0.0, 0.0, 0.0),
            glm.vec3(0.0, 0.0, 0.0),
            glm.vec3(0.0, 0.0, 0.0),
            glm.vec3(0.0, 0.0, 0.0),
            glm.vec3(0.0, 0.0, 0.0),
            glm.vec3(0.0, 0.0, 0.0),
            glm.vec3(0.0, 0.0, 0.0),
            glm.vec3(0.0, 0.0, 0.0),
        ]
        self.apply_cols()
        self.kick = 0
        self.effect_index = 0
        self.effects = [
            self.effect_1,
            self.effect_3,
            self.effect_4,
            self.effect_5,
            self.effect_6,
            self.effect_7,
            self.effect_8,
            self.effect_9,
            self.effect_10,
            self.effect_11,
            self.effect_12,
            self.effect_13,
            self.effect_14,
            self.effect_15,
            self.effect_16,
        ]

    def initUniformsBinding(self):
        binding = {
            "d11": "d11",
            "d12": "d12",
            "d13": "d13",
            "d21": "d21",
            "d22": "d22",
            "d23": "d23",
            "d31": "d31",
            "d32": "d32",
            "d33": "d33",
        }
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def self_whole_triangle(self, id, col):
        self.colors[id * 3 + 0] = col
        self.colors[id * 3 + 1] = col
        self.colors[id * 3 + 2] = col

    def set_all(self, col):
        self.self_whole_triangle(0, col)
        self.self_whole_triangle(1, col)
        self.self_whole_triangle(2, col)

    def exterior(self, col):
        self.colors[0] = col
        self.colors[2] = col

        self.colors[0 + 3] = col
        self.colors[1 + 3] = col

        self.colors[1 + 6] = col
        self.colors[2 + 6] = col

    def interior(self, col):
        self.colors[1] = col
        self.colors[2 + 3] = col
        self.colors[0 + 6] = col

    def effect_5(self, af=None):
        self.set_all(BLACK)
        col = self.get_col()[(self.kick // 3) % len(self.get_col())]
        if self.kick % 2 == 0:
            self.exterior(col)
        else:
            self.interior(col)

    def effect_13(self, af=None):
        col = self.get_col()[(self.kick) % len(self.get_col())] * af["decaying_kick"]
        if self.kick % 2 == 0:
            self.exterior(col)
        else:
            self.interior(col)

    def effect_3(self, af=None):
        col = self.get_col()[(self.kick // 3) % len(self.get_col())]
        p = af["decaying_kick"]
        self.set_all(col * p)

    def effect_6(self, af=None):
        col = self.get_col()[(self.kick) % len(self.get_col())]
        p = af["decaying_kick"]
        self.set_all(col * p)

    def effect_7(self, af=None):
        for i in range(9):
            self.colors[i] = self.get_col()[(self.kick + i) % len(self.get_col())]

    def effect_14(self, af=None):
        self.set_all(BLACK)
        self.colors[self.kick % 9] = self.get_col()[(self.kick) % len(self.get_col())]

    def effect_15(self, af=None):
        self.set_all(BLACK)
        self.colors[self.kick % 9] = self.get_col2()[(self.kick) % len(self.get_col2())]

    def effect_16(self, af=None):
        for i in range(9):
            self.colors[i] = self.get_col2()[(self.kick + i) % len(self.get_col2())]

    def effect_12(self, af=None):
        for i in range(9):
            self.colors[i] = (
                self.get_col()[(self.kick + i) % len(self.get_col())]
                * af["decaying_kick"]
            )

    def effect_8(self, af=None):
        self.set_all(BLACK)
        self.interior(self.get_col()[self.kick % len(self.get_col())])
        self.exterior(self.get_col()[(self.kick + 1) % len(self.get_col())])

    def effect_9(self, af=None):
        self.self_whole_triangle(
            0, self.get_col()[(self.kick + 0) % len(self.get_col())]
        )
        self.self_whole_triangle(
            1, self.get_col()[(self.kick + 1) % len(self.get_col())]
        )
        self.self_whole_triangle(
            2, self.get_col()[(self.kick + 2) % len(self.get_col())]
        )

    def effect_10(self, af=None):
        self.set_all(BLACK)
        self.interior(
            self.get_col()[self.kick % len(self.get_col())] * af["decaying_kick"]
        )

    def effect_11(self, af=None):
        self.set_all(BLACK)
        self.exterior(
            self.get_col()[self.kick % len(self.get_col())] * af["decaying_kick"]
        )

    def effect_1(self, af=None):
        col = self.get_col()[(self.kick // 3) % len(self.get_col())]
        self.set_all(BLACK)
        self.self_whole_triangle(self.kick % 3, col)

    def effect_4(self, af=None):
        col = self.get_col()[(self.kick) % len(self.get_col())]
        self.set_all(BLACK)
        self.self_whole_triangle(self.kick % 3, col)

    def upp(self, b):
        self.effect_index = self.effect_index + 1

    def down(self, b):
        self.effect_index = self.effect_index - 1

    def updateParams(self, af=None):
        if af is None:
            return
        if af["on_tempo"] > 0.9 and not self.wo:
            self.wo = True
            self.kick = self.kick + 1
        if af["on_tempo"] <= 0.9:
            self.wo = False
        if self.kick % 30 == 0:
            self.kick = 1
            self.effect_index = random.randrange(0, len(self.effects))
        self.effects[self.effect_index % len(self.effects)](af)
        self.apply_cols()
        if self.light_engine:
            self.light_engine.shader_buffer[0] = self.colors[0].x
            self.light_engine.shader_buffer[1] = self.colors[0].y
            self.light_engine.shader_buffer[2] = self.colors[0].z

            self.light_engine.shader_buffer[3] = self.colors[1].x
            self.light_engine.shader_buffer[4] = self.colors[1].y
            self.light_engine.shader_buffer[5] = self.colors[1].z

            self.light_engine.shader_buffer[6] = self.colors[2].x
            self.light_engine.shader_buffer[7] = self.colors[2].y
            self.light_engine.shader_buffer[8] = self.colors[2].z

            self.light_engine.shader_buffer[9] = self.colors[3].x
            self.light_engine.shader_buffer[10] = self.colors[3].y
            self.light_engine.shader_buffer[11] = self.colors[3].z

            self.light_engine.shader_buffer[12] = self.colors[4].x
            self.light_engine.shader_buffer[13] = self.colors[4].y
            self.light_engine.shader_buffer[14] = self.colors[4].z

            self.light_engine.shader_buffer[15] = self.colors[5].x
            self.light_engine.shader_buffer[16] = self.colors[5].y
            self.light_engine.shader_buffer[17] = self.colors[5].z

            self.light_engine.shader_buffer[18] = self.colors[6].x
            self.light_engine.shader_buffer[19] = self.colors[6].y
            self.light_engine.shader_buffer[20] = self.colors[6].z

            self.light_engine.shader_buffer[21] = self.colors[7].x
            self.light_engine.shader_buffer[22] = self.colors[7].y
            self.light_engine.shader_buffer[23] = self.colors[7].z

            self.light_engine.shader_buffer[24] = self.colors[8].x
            self.light_engine.shader_buffer[25] = self.colors[8].y
            self.light_engine.shader_buffer[26] = self.colors[8].z

    def norender(self):
        return self.fbos[0].color_attachments[0]

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_TRIFORCE)
class TriforceNode(ShaderNode, Scene):
    op_title = "Triforce"
    op_code = OP_CODE_TRIFORCE
    content_label = ""
    content_label_objname = "shader_Triforce"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Triforce(
            ctx=self.scene.ctx,
            win_size=(1920, 1080),
            light_engine=scene.app.light_engine,
        )
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            output_Triforce = self.program.norender()
        else:
            output_Triforce = self.program.render(audio_features)

        return output_Triforce
