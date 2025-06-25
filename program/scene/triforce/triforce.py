from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_TRIFORCE = name_to_opcode("Triforce")


@register_program(OP_CODE_TRIFORCE)
class Triforce(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Triforce"

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

    def initParams(self):
        pass

    def initUniformsBinding(self):
        binding = {}
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def updateParams(self, af=None):
        if af is None:
            return

    def norender(self):
        return self.fbos[0].color_attachments[0]

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
        self.program = Triforce(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            output_Triforce = self.program.norender()
        else:
            output_Triforce = self.program.render(audio_features)

        return output_Triforce
