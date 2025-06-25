from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Gate
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_KICKCHANGE = name_to_opcode("kickchange")


@register_program(OP_CODE_KICKCHANGE)
class OnKickChange(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "OnKickChange"

        self.initProgram()
        self.initFBOSpecifications()
        self.initParams()
        self.initUniformsBinding()

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
        frag_path = join(dirname(__file__), "kick_change_gate.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.which = 0
        self.iChannel0 = 0
        self.was_on_kick = False
        self.num_kick = 0
        self.count = 1

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "iChannel0": "iChannel0",
            "which": "which",
        }
        self.add_text_edit_cpu_adaptable_parameter("num_kick", self.count, lambda: 0)
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def updateParams(self, l, af):
        if af is None or self.already_called:
            return

        self.count = int(
            self.getCpuAdaptableParameters()["program"]["num_kick"]["eval_function"][
                "value"
            ]
        )
        if af["on_kick"] and not self.was_on_kick:
            self.num_kick += 1
            self.was_on_kick = True
        elif not af["on_kick"]:
            self.was_on_kick = False
        if self.num_kick >= self.count:
            self.which = (self.which + 1) % l
            self.num_kick = 0

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, l, af=None):
        self.updateParams(l, af)
        self.bindUniform(af)
        return textures[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_KICKCHANGE)
class OnKickChangeNode(ShaderNode, Gate):
    op_title = "OnKickChange"
    op_code = OP_CODE_KICKCHANGE
    content_label = ""
    content_label_objname = "shader_OnKickChange"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1, 2, 3, 4], outputs=[3])
        self.program = OnKickChange(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        l = len(input_nodes)
        if l == 0:
            return self.program.norender()

        if l == 1:
            texture = input_nodes[0].render(audio_features)
            return texture
        texture = input_nodes[self.program.which].render(audio_features)
        output_texture = self.program.render([texture], l, audio_features)
        return output_texture
