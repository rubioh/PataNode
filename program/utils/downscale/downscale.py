from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Utils
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_DOWNSCALE = name_to_opcode("downscale")


@register_program(OP_CODE_DOWNSCALE)
class Downscale(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Downscale"

        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
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
        frag_path = join(dirname(__file__), "downscale.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initUniformsBinding(self):
        binding = {"iChannel0": "iChannel0", "iResolution": "win_size"}
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def initParams(self):
        self.iChannel0 = 0

    def updateParams(self, af=None):
        if af is None:
            return

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.bindUniform(af)
        self.updateParams(af)

        textures[0].use(0)

        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_DOWNSCALE)
class DownscaleNode(ShaderNode, Utils):
    op_title = "Downscale"
    op_code = OP_CODE_DOWNSCALE
    content_label = ""
    content_label_objname = "shader_downscale"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = Downscale(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()

        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()

        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
