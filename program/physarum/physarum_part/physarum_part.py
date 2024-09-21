from os.path import dirname, basename, isfile, join
import time
import numpy as np
import moderngl as mgl
from pyrr import Matrix44

from program.program_conf import (
    SQUARE_VERT_PATH,
    get_square_vertex_data,
    register_program,
    name_to_opcode,
)
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Physarum
from node.node_conf import register_node


OP_CODE_PHYSARUMPART = name_to_opcode("physa1")


@register_program(OP_CODE_PHYSARUMPART)
class PhysarumPart(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Spiral Particules"

        self.initParams()
        self.initFBOSpecifications()
        self.initProgram()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, "f4", True],
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])
            self.fbos_depth_requirement.append(specification[3])
        self.initVBOs()

    def initVBOs(self):
        self.vbo1 = self.ctx.buffer(reserve=self.N_part * 16)
        self.vbo2 = self.ctx.buffer(reserve=self.N_part * 16)

    def initProgram(self, reload=False):
        vert_path = join(dirname(__file__), "particules/draw.vert")
        frag_path = join(dirname(__file__), "particules/draw.frag")
        vao_binding = [(self.vbo1, "4f4", "in_infos")]
        self.loadProgramToCtx(
            vert_path, frag_path, reload, "draw_", vao_binding=vao_binding
        )

        vert_path = join(dirname(__file__), "particules/transform.vert")
        frag_path = None
        varyings = ["out_infos"]
        vao_binding = [(self.vbo1, "4f4", "in_infos")]
        self.loadProgramToCtx(
            vert_path,
            frag_path,
            reload,
            "transform_",
            vao_binding=vao_binding,
            varyings=varyings,
        )

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "physarum_part.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        # self.N_part = 150000*16
        self.N_part = 1000000
        self.part_size = 1

        self.iFrame = -1

        self.sensor_direction = 1.2  # 22.5/180*np.pi # theta
        self.update_direction = 0.5  # 22.5/180*np.pi # phi
        self.trail_thresh = 2500  # TODO
        self.velocity_rate = 2.0
        self.sensor_length = 10

        self.to_center_amount = 0

        self.Trail = 0
        self.SeedTex = 1

        W = (self.win_size[0] * 2, self.win_size[1] * 2)
        self.seed_texture = self.ctx.texture(size=W, components=4, dtype="f4")
        random = np.float32(np.random.rand(*W, 4))
        self.seed_texture.write(random)

    def updateParams(self, af):
        self.iFrame += 1
        if af is None:
            return
        return

    def initUniformsBinding(self):
        binding = {}
        super().initUniformsBinding(binding, program_name="draw_")
        binding = {
            "iFrame": "iFrame",
            "part_size": "part_size",
            "iResolution": "win_size",
            "sensor_direction": "sensor_direction",
            "update_direction": "update_direction",
            "trail_thresh": "trail_thresh",
            "velocity_rate": "velocity_rate",
            "sensor_length": "sensor_length",
            "to_center_amount": "to_center_amount",
            "Trail": "Trail",
            "SeedTex": "SeedTex",
        }
        super().initUniformsBinding(binding, program_name="transform_")
        self.addProtectedUniforms(["iChannel0", "Trail", "SeedTex"])

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="draw_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="transform_")

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.ctx.point_size = self.part_size
        self.ctx.copy_buffer(self.vbo1, self.vbo2)
        textures[0].use(0)
        self.seed_texture.use(1)
        self.transform_vao.transform(self.vbo2, mgl.POINTS, self.N_part)

        self.fbos[0].clear()
        self.fbos[0].use()
        self.ctx.enable(mgl.BLEND)
        self.ctx.blend_equation = mgl.FUNC_ADD
        self.ctx.blend_func = mgl.ONE, mgl.ONE
        self.draw_vao.render(mgl.POINTS, self.N_part)
        self.ctx.disable(mgl.BLEND)
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_PHYSARUMPART)
class PhysarumPartNode(ShaderNode, Physarum):
    op_title = "Physarum particules"
    op_code = OP_CODE_PHYSARUMPART
    content_label = ""
    content_label_objname = "shader_physarum_part"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = PhysarumPart(ctx=self.scene.ctx, win_size=self.win_size)
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()
        self.already_called = True
        input_nodes = self.getShaderInputs()
        if not len(input_nodes):
            return self.program.norender()
        if input_nodes[0].already_called:
            texture = input_nodes[0].program.norender()
        else:
            texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
