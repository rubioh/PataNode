import yaml

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Utils
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_OFFSET = name_to_opcode("offset")


@register_program(OP_CODE_OFFSET)
class Offset(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "offset"

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
        frag_path = join(dirname(__file__), "offset.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.iChannel0 = 1

        with open("resources/zozo_conf.yaml") as stream:
            arch_conf = yaml.safe_load(stream)["arch"]
            self.y_offset = float(arch_conf["y_offset"])
            self.x_offset = float(arch_conf["x_offset"])
            self.zoom = arch_conf["zoom"]

        self.x_offset_fine = 0.0
        self.y_offset_fine = 0.0

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "x_offset": "x_offset",
            "y_offset": "y_offset",
            "x_offset_fine": "x_offset_fine",
            "y_offset_fine": "y_offset_fine",
            "zoom": "zoom",
            "iChannel0": "iChannel0",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0", "x_offset", "y_offset"])

    def updateParams(self, af):
        if af is None:
            return

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.bindUniform(af)
        (self.updateParams(af),)
        textures[0].repeat_x = False
        textures[0].repeat_y = False
        textures[0].border_color = (0.0, 0.0, 0.0, 0.0)
        textures[0].use(1)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_OFFSET)
class OffsetNode(ShaderNode, Utils):
    op_title = "Offset"
    op_code = OP_CODE_OFFSET
    content_label = ""
    content_label_objname = "shader_offset"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = Offset(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()

        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()

        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
