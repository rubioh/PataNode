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

PAL1 = glm.vec3(255.0 / 255.0, 1.0 / 255.0, 21.0 / 255.0)
PAL2 = glm.vec3(79.0 / 255.0, 23.0 / 255.0, 135.0 / 255.0)
PAL3 = glm.vec3(35.0 / 255.0, 54.0 / 255.0, 255.0 / 255.0)
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
        self.l1 = self.colors[0]
        self.l2 = self.colors[1]
        self.l3 = self.colors[2]
        self.l4 = self.colors[3]
        self.l5 = self.colors[4]
        self.l6 = self.colors[5]

        self.strobe1 = self.strobes[0]
        self.strobe2 = self.strobes[1]
        self.strobe3 = self.strobes[2]
        self.strobe4 = self.strobes[3]
        self.strobe5 = self.strobes[4]
        self.strobe6 = self.strobes[5]
        #     dj     #
        # l1      l4 #
        # l2      l5 #
        # l3      l6 #

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
        ]
        self.strobes = [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]

        self.l1 = self.colors[0]
        self.l2 = self.colors[1]
        self.l3 = self.colors[2]
        self.l4 = self.colors[3]
        self.l5 = self.colors[4]
        self.l6 = self.colors[5]

        self.strobe1 = 0.0
        self.strobe2 = 0.0
        self.strobe3 = 0.0
        self.strobe4 = 0.0
        self.strobe5 = 0.0
        self.strobe6 = 0.0
        self.apply_cols()
        self.kick = 0
        self.effect_index = 0
        self.effects = [
            self.effect_1,
            self.effect_2,
            self.effect_3,
            self.effect_4,
            self.effect_5,
            self.effect_6,
            self.strobe,
        ]

    #        self.effects = [
    #            self.effect_0
    #        ]

    def initUniformsBinding(self):
        binding = {
            "l1": "l1",
            "l2": "l2",
            "l3": "l3",
            "l4": "l4",
            "l5": "l5",
            "l6": "l6",
        }
        super().initUniformsBinding(binding, program_name="")
        col = self.get_col()[(self.kick) % len(self.get_col())]

    def set_all(self, col):
        for i in range(len(self.colors)):
            self.colors[i] = col

    def set_all_strobe(self, value):
        for i in range(len(self.strobes)):
            self.strobes[i] = value

    def updateParams(self, af=None):
        self.set_all(glm.vec3(0.0))
        self.set_all_strobe(1.0)
        if af is None:
            return
        if af["on_tempo"] > 0.9 and not self.wo:
            self.wo = True
            self.kick = self.kick + 1
        if af["on_tempo"] <= 0.9:
            self.wo = False
        if self.kick % 30 == 0:
            self.kick = 1
            self.effect_index = random.randrange(0, len(self.effects) - 1)
        self.effects[self.effect_index % len(self.effects)](af)
        self.apply_cols()
        offset = 0
        indirect = [0, 1, 2, 3, 4, 5]
        strobe_offset = [7, 7, 7, 7, 7, 7]
        if self.light_engine:
            for i in range(len(self.colors)):
                self.light_engine.shader_buffer[offset] = self.colors[indirect[i]].x
                self.light_engine.shader_buffer[offset + 1] = self.colors[indirect[i]].y
                self.light_engine.shader_buffer[offset + 2] = self.colors[indirect[i]].z
                self.light_engine.shader_buffer[offset + 6] = 1.0

                #                self.light_engine.shader_buffer[offset + 7] = 1.0
                #            self.light_engine.shader_buffer[offset + 4] = 1.#self.colors[indirect[i]].x
                #            self.light_engine.shader_buffer[offset + 5] = 1.#self.colors[indirect[i]].x
                #            self.light_engine.shader_buffer[offset + strobe_offset[i]] = self.strobes[indirect[i]]
                offset = offset + 15

    def effect_0(self, af):
        self.colors[0] = glm.vec3(1.0, 0.0, 0.0)
        self.colors[1] = glm.vec3(0.0, 1.0, 0.0)
        self.colors[2] = glm.vec3(0.0, 0.0, 1.0)
        self.colors[3] = glm.vec3(1.0, 0.0, 1.0)
        self.colors[4] = glm.vec3(0.0, 1.0, 1.0)
        self.colors[5] = glm.vec3(1.0, 1.0, 0.0)

    def effect_1(self, af):
        self.colors[(self.kick) % 6] = self.get_col()[
            (self.kick // 2) % len(self.get_col())
        ]

    def effect_2(self, af):
        for i in range(len(self.colors)):
            self.colors[i] = (
                self.get_col()[(self.kick + i) % len(self.get_col())] * af["on_kick"]
            )

    def effect_3(self, af):
        self.colors[self.kick % 3] = self.get_col()[0]
        self.colors[self.kick % 3 + 3] = self.get_col()[0]

    def effect_4(self, af):
        self.colors[self.kick % 3] = self.get_col()[1]
        self.colors[self.kick % 3 + 3] = self.get_col()[1]

    def effect_5(self, af):
        indirect = [2, 1, 5, 3, 4, 0]
        self.colors[indirect[self.kick % 6]] = self.get_col()[0]

    def effect_6(self, af):
        self.colors[0 + (self.kick % 2) * 3] = self.get_col()[1]
        self.colors[1 + (self.kick % 2) * 3] = self.get_col()[1]
        self.colors[2 + (self.kick % 2) * 3] = self.get_col()[1]

    def strobe(self, af):
        self.set_all(glm.vec3(1.0))
        for i in range(len(self.strobes)):
            self.strobes[i] = 0.4

    def upp(self, b):
        self.effect_index = (self.effect_index + 1) % len(self.effects)

    def down(self, b):
        self.effect_index = (self.effect_index - 1) % len(self.effects)

    def norender(self):
        return self.fbos[0].color_attachments[0]

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")
        self.programs_uniforms.programs[""]["l1"] = self.l1
        self.programs_uniforms.programs[""]["l2"] = self.l2
        self.programs_uniforms.programs[""]["l3"] = self.l3
        self.programs_uniforms.programs[""]["l4"] = self.l4
        self.programs_uniforms.programs[""]["l5"] = self.l5
        self.programs_uniforms.programs[""]["l6"] = self.l6

        self.programs_uniforms.programs[""]["strobe1"] = self.strobe1
        self.programs_uniforms.programs[""]["strobe2"] = self.strobe2
        self.programs_uniforms.programs[""]["strobe3"] = self.strobe3
        self.programs_uniforms.programs[""]["strobe4"] = self.strobe4
        self.programs_uniforms.programs[""]["strobe5"] = self.strobe5
        self.programs_uniforms.programs[""]["strobe6"] = self.strobe6

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

    # 4 lights effects

    def effect_41(self, af):
        self.colors[(self.kick) % 4] = self.get_col()[
            (self.kick // 2) % len(self.get_col())
        ]

    def effect_42(self, af):
        for i in range(len(self.colors) - 1):
            self.colors[i] = (
                self.get_col()[(self.kick + i) % len(self.get_col())] * af["on_kick"]
            )

    def effect_43(self, af):
        self.colors[self.kick % 2] = self.get_col()[0]
        self.colors[self.kick % 2 + 2] = self.get_col()[0]

    def effect_44(self, af):
        self.colors[self.kick % 2] = self.get_col()[1]
        self.colors[self.kick % 2 + 2] = self.get_col()[1]

    def effect_45(self, af):
        indirect = [3, 2, 0, 1]
        self.colors[indirect[self.kick % 4]] = self.get_col()[0]

    def effect_46(self, af):
        self.colors[0 + (self.kick % 2) * 2] = self.get_col()[1]
        self.colors[1 + (self.kick % 2) * 2] = self.get_col()[1]
