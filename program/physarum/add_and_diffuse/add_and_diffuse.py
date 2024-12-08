from os.path import dirname, join

from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode
from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Physarum


OP_CODE_ADD_AND_DIFFUSE = name_to_opcode("add_and_diffuse")


@register_program(OP_CODE_ADD_AND_DIFFUSE)
class AddAndDiffuse(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "AddAndDiffuse"

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
        frag_path = join(dirname(__file__), "add_and_diffuse.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.AddTexture = 1
        self.BaseTexture = 2

        self.decay_rate = 0.95
        self.diffuse_amount = 0.5

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "AddTexture": "AddTexture",
            "BaseTexture": "BaseTexture",
            "decay_rate": "decay_rate",
            "diffuse_amount": "diffuse_amount",
        }

        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["AddTexture", "BaseTexture"])

    def updateParams(self, af):
        if af is None:
            return

        pass

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        textures[0].use(2)
        textures[1].use(1)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_ADD_AND_DIFFUSE)
class AddAndDiffuseNode(ShaderNode, Physarum):
    op_title = "AddAndDiffuse"
    op_code = OP_CODE_ADD_AND_DIFFUSE
    content_label = ""
    content_label_objname = "shader_add_and_diffuse"

    def __init__(self, scene):
        super().__init__(scene, inputs=[2, 1], outputs=[3])
        self.program = AddAndDiffuse(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        print(self, self.already_called)

        if self.already_called:
            return self.program.norender()

        self.already_called = True
        input_nodes = self.getShaderInputs()

        if not len(input_nodes):
            return self.program.norender()

        if input_nodes[0].already_called:
            texture = input_nodes[0].program.norender()
        else:
            texture = input_nodes[0].render(audio_features)

        if input_nodes[1].already_called:
            add_texture = input_nodes[1].program.norender()
        else:
            add_texture = input_nodes[1].render(audio_features)

        output_texture = self.program.render([texture, add_texture], audio_features)
        return output_texture
