from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import Colors, ShaderNode
from program.colors.value_gradient.palette_preview import PalettePreviewWindow
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, name_to_opcode, register_program

OP_CODE_VALUEGRADIENT = name_to_opcode("valuegradient")


@register_program(OP_CODE_VALUEGRADIENT)
class ValueGradient(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Value Gradient"

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
        frag_path = join(dirname(__file__), "value_gradient.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 1
        # One full turn of the palette across the luminance range.
        self.frequency = 1.0
        # Evenly spread phases -- the classic rainbow starting point.
        self.phase_r = 0.0
        self.phase_g = 0.33
        self.phase_b = 0.67
        self.saturation = 1.0
        self.dry_wet = 1

        self.initParameterDoc(
            "dry_wet",
            "How much of the effect is mixed over the node's input. 1.0 is "
            "the effect at full strength, which is what every scene saved "
            "before this parameter existed renders; 0 passes the input "
            "through untouched, so the node can be faded out without being "
            "unplugged.",
            default=1.0,
            minimum=0.0,
            maximum=1.0,
        )

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "iChannel0": "iChannel0",
            "frequency": "frequency",
            "phase_r": "phase_r",
            "phase_g": "phase_g",
            "phase_b": "phase_b",
            "saturation": "saturation",
            "dry_wet": "dry_wet",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def updateParams(self, af):
        if af is None:
            return

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)

        textures[0].use(1)

        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_VALUEGRADIENT)
class ValueGradientNode(ShaderNode, Colors):
    op_title = "Value Gradient"
    op_code = OP_CODE_VALUEGRADIENT
    content_label = ""
    content_label_objname = "shader_value_gradient"
    preview_window_class = PalettePreviewWindow

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = ValueGradient(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            return self.program.norender()

        input_nodes = self.getShaderInputs()

        if not len(input_nodes):
            return self.program.norender()

        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
