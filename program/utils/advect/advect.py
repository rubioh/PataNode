from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Utils
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, name_to_opcode, register_program

OP_CODE_ADVECT = name_to_opcode("advect")


@register_program(OP_CODE_ADVECT)
class Advect(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Advect"

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
        frag_path = join(dirname(__file__), "advect.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 0
        self.iChannel1 = 1
        self.advect_amount = 1.0

        self.initParameterDoc(
            "advect_amount",
            "How far content is dragged per frame by the flow field on "
            "iChannel1. Motion Flow's field is already one frame of uv "
            "displacement, so 1.0 is the physically correct amount; raise it "
            "for a stronger streak/smear, lower it for a subtler warp.",
            default=1.0,
            minimum=0.0,
            maximum=8.0,
        )

    def initUniformsBinding(self):
        binding = {
            "iChannel0": "iChannel0",
            "iChannel1": "iChannel1",
            "iResolution": "win_size",
            "advect_amount": "advect_amount",
        }
        super().initUniformsBinding(binding, program_name="")

        self.addProtectedUniforms(["iChannel0", "iChannel1"])

    def updateParams(self, af):
        if af is None:
            return

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.bindUniform(af)
        self.updateParams(af)

        if textures[0] is not None:
            # Clamp to a transparent border rather than repeat, so content
            # dragged past the edge fades out instead of wrapping around from
            # the opposite side of the image.
            textures[0].repeat_x = False
            textures[0].repeat_y = False
            textures[0].border_color = (0.0, 0.0, 0.0, 0.0)
            textures[0].use(0)

        if textures[1] is not None:
            textures[1].use(1)

        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_ADVECT)
class AdvectNode(ShaderNode, Utils):
    op_title = "Advect"
    op_code = OP_CODE_ADVECT
    content_label = ""
    content_label_objname = "shader_advect"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1, 2], outputs=[3])
        self.program = Advect(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()

        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()

        texture0 = input_nodes[0].render(audio_features)
        texture1 = (
            input_nodes[1].render(audio_features) if len(input_nodes) > 1 else None
        )

        output_texture = self.program.render([texture0, texture1], audio_features)
        return output_texture
