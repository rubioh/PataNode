import moderngl
import numpy as np

from os.path import dirname,join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Map
from program.map.mapping.earcut import earcut
from program.program_base import ProgramBase
from program.program_conf import register_program, name_to_opcode


OP_CODE_MAPPING = name_to_opcode("Mapping")

def read_file(path):
    f = open(path, "r")
    return f.read()

@register_program(OP_CODE_MAPPING)
class Mapping(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Mapping"
        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
#       self.initUniformsBinding()
        self.polygons = [[0., 0., 0., 0.,
                            0., 1., 0., 1.,
                            1., 1., 1., 1.,
                        1., 0., 1., 0. ],
                        [0., 0., 0., 0.,
                            0., 1., 0., 1.,
                            1., 1., 1., 1.,
                            1., 0., 1., 0. ] ]
        self.vaos = []

    def updatePolygons(self, new_polygons):
        self.needsEarcut = True
        self.polygons = new_polygons

    def initFBOSpecifications(self):
        self.required_fbos = 2
        fbos_specification = [[self.win_size, 4, "f4"], [self.win_size, 4, "f4"] ]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = join(dirname(__file__), "mapping_vertex.glsl")
        frag_path = join(dirname(__file__), "mapping.glsl")
        code_version = "#version "
        code_version += str(3) + str(3) + str("0 core\n")
        self.program = self.ctx.program(
            vertex_shader=read_file(vert_path), fragment_shader=read_file(frag_path)
        )

    def initParams(self):
        self.needsEarcut = True
        self.wireframe = False

    def initUniformsBinding(self):
        binding = {
        }
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def updateEarcut(self):
        self.vaos = []
        for i, p in enumerate(self.polygons):
            n_p = []
            vertex_pos = []
            vertex_tcs = []

            for j in range(len(p) // 4):
                n_p.append(p[j * 4])
                n_p.append(p[j * 4+ 1])
                vertex_pos.append(p[j * 4])
                vertex_pos.append(p[j * 4 + 1])
                vertex_tcs.append(p[j * 4 + 2])
                vertex_tcs.append(p[j * 4 + 3])

            indices = earcut(n_p)
            gpu_vertex_buffer = np.array([],dtype='f4')
            gpu_tcs_buffer = np.array([],dtype='f4')
            if i  % 2 == 0:
                for idx in indices:
                    gpu_vertex_buffer = np.append(gpu_vertex_buffer,   float (vertex_pos[idx * 2] ) )
                    gpu_vertex_buffer = np.append(gpu_vertex_buffer, float(vertex_pos[idx * 2 + 1]) )
                    gpu_tcs_buffer = np.append(gpu_tcs_buffer, float(vertex_tcs[idx * 2 + 0]) )
                    gpu_tcs_buffer = np.append(gpu_tcs_buffer, float(vertex_tcs[idx * 2 + 1]) )
            else:
                for idx in indices:
                    gpu_vertex_buffer = np.append(gpu_vertex_buffer,   float (vertex_pos[idx * 2] ) )
                    gpu_vertex_buffer = np.append(gpu_vertex_buffer, float(vertex_pos[idx * 2 + 1]) )
                    gpu_tcs_buffer = np.append(gpu_tcs_buffer, float(vertex_pos[idx * 2 + 0]) )
                    gpu_tcs_buffer = np.append(gpu_tcs_buffer, float(vertex_pos[idx * 2 + 1]) )
            gpu_vertex_buffer = gpu_vertex_buffer.astype("f4")
            gpu_tcs_buffer = gpu_tcs_buffer.astype("f4")
            self.vaos.append( self.ctx.vertex_array(self.program,
                [(self.ctx.buffer(gpu_vertex_buffer), "2f", "in_position"),
                (self.ctx.buffer(gpu_tcs_buffer), "2f", "in_tcs")]) )

    def updateParams(self, af=None):
        if self.needsEarcut:
            self.needsEarcut = False
            self.updateEarcut()

    def norender(self):
        return self.fbos[0].color_attachments[0]

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.program["iChannel0"] = 0

        textures[0].use(0)
        self.fbos[0].use()
        self.fbos[0].clear()
        self.fbos[1].clear()

        for vao in self.vaos[1::2]:
            vao.render()

        self.fbos[0].color_attachments[0].use(0)
        self.fbos[1].use()

        for vao in self.vaos[0::2]:
            vao.render()

        if self.wireframe:
            self.program["white"] = 1
            shape = moderngl.LINE_STRIP

            self.fbos[1].use()
#            self.fbos[0].clear()
#            self.fbos[1].clear()

            for vao in self.vaos[1::2]:
                vao.render(moderngl.LINE_STRIP)

            self.fbos[0].color_attachments[0].use(0)
            self.fbos[1].use()

            for vao in self.vaos[0::2]:
                vao.render(moderngl.LINE_STRIP)

        self.program["white"] = 0

        return self.fbos[1].color_attachments[0]

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
