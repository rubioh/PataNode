from os.path import dirname,join

from program.program_conf import (
    SQUARE_VERT_PATH,
    register_program,
    name_to_opcode,
)
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Map
from node.node_conf import register_node

OP_CODE_MAPPING = name_to_opcode("Mapping")

@register_program(OP_CODE_MAPPING)
class Mapping(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Mapping"
        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.polygons = [[0., 0., 0., 0.,  
                            0., 1., 0., 1.,
                            1., 1., 1., 1.,
                        1., 0., 1., 0. ],
                        [0., 0., 0., 0.,  
                            0., 1., 0., 1.,
                            1., 1., 1., 1.,
                            1., 0., 1., 0. ] ]

    def updatePolygons(self, new_polygons):
        self.polygons = new_polygons

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [[self.win_size, 4, "f4"]]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "mapping.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        pass

    def initUniformsBinding(self):
        binding = {
        }
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def updateParams(self, af=None):
        pass

    def norender(self):
        return self.fbos[0].color_attachments[0]

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.program["iChannel0"] = 0
        textures[0].use(0)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

@register_node(OP_CODE_MAPPING)
class MappingNode(ShaderNode, Map):
    op_title = "Mapping"
    op_code = OP_CODE_MAPPING
    content_label = ""
    content_label_objname = "shader_mapping"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = Mapping(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
