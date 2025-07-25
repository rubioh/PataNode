from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Utils
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_RECONSTRUCT = name_to_opcode("Reconstruct")


@register_program(OP_CODE_RECONSTRUCT)
class Reconstruct(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Reconstruct"

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
        frag_path = join(dirname(__file__), "Reconstruct.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 1
        self.iChannel1 = 2
        self.texture1 = None
        self.texture2 = None
        self.frame = 0

    def initUniformsBinding(self):
        binding = {
            "iChannel0": "iChannel0",
            "iChannel1": "iChannel1",
            "iResolution": "win_size",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])
        self.addProtectedUniforms(["iChannel1"])

    def updateParams(self, af):
        self.iChannel0 = 1
        self.iChannel1 = 2
        self.frame = self.frame + 1

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, af=None):
        self.updateParams(af)

        if self.texture1 is None or self.texture2 is None:
            return self.fbos[0].color_attachments[0]

        self.bindUniform(af)
        self.texture1.use(1)
        self.texture2.use(2)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_RECONSTRUCT)
class ReconstructNode(ShaderNode, Utils):
    op_title = "Reconstruct"
    op_code = OP_CODE_RECONSTRUCT
    content_label = ""
    content_label_objname = "shader_Reconstruct"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[2])
        self.program = Reconstruct(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()

        print("frame:", self.program.frame)

        if self.program.frame % 2:
            self.program.texture1 = input_nodes[0].render(audio_features, 0)
            print("oui")
        else:
            self.program.texture2 = input_nodes[0].render(audio_features, 1)
            print("non")

        if self.program.texture1 is None or self.program.texture2 is None:
            self.program.texture1 = input_nodes[0].render(audio_features, 0)
            self.program.texture2 = input_nodes[0].render(audio_features, 0)

        output_texture = self.program.render(audio_features)
        return output_texture
