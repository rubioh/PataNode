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

from node.shader_node_base import ShaderNode, Particles
from node.node_conf import register_node


OP_CODE_SPIRALPARTICULES = name_to_opcode("spiralparticules")


@register_program(OP_CODE_SPIRALPARTICULES)
class SpiralParticules(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Spiral Particules"

        self.initParams()
        self.initFBOSpecifications()
        self.initProgram()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        self.required_fbos = 4
        fbos_specification = [
            [self.win_size, 4, "f4", True],
            [self.win_size, 4, "f4", True],
            [self.win_size, 4, "f4", False],
            [self.win_size, 4, "f4", False],
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
        vert_path = join(dirname(__file__), "part/draw.vert")
        frag_path = join(dirname(__file__), "part/draw.frag")
        vao_binding = [(self.vbo1, "4f4", "in_position")]
        self.loadProgramToCtx(
            vert_path, frag_path, reload, "draw_", vao_binding=vao_binding
        )

        vert_path = join(dirname(__file__), "part/draw.vert")
        frag_path = join(dirname(__file__), "part/alpha.frag")
        vao_binding = [(self.vbo1, "4f4", "in_position")]
        self.loadProgramToCtx(
            vert_path, frag_path, reload, "alpha_", vao_binding=vao_binding
        )

        vert_path = join(dirname(__file__), "part/transform.vert")
        frag_path = None
        varyings = ["out_pos", "out_prev"]
        vao_binding = [(self.vbo1, "4f4 4f4", "in_pos", "prev_pos")]
        self.loadProgramToCtx(
            vert_path,
            frag_path,
            reload,
            "transform_",
            vao_binding=vao_binding,
            varyings=varyings,
        )
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "spiralparticules.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, "")

    def initParams(self):
        self.N_part = 15000
        self.N_part_final = self.N_part // 2

        # MVP
        self.aspect_ratio = self.win_size[0] / self.win_size[1]
        self.near = 1
        self.far = 100
        self.fov = 60
        rotation = Matrix44.from_eulers((0.0, 0.0, 0.0), dtype="f4")
        translation = Matrix44.from_translation((0, 0, -10), dtype="f4")
        self.modelview = translation * rotation
        self.projection = Matrix44.perspective_projection(
            self.fov, self.aspect_ratio, self.near, self.far, dtype="f4"
        )
        self.timeaf = 0
        self.time = 0
        self.iFrame = 0
        self.next = 0
        self.mnext = 0
        self.sens_m = 1
        self.go_mnext = 1
        self.mod_fract = 1
        self.go_mf = 1
        self.dt = 0.1

        self.angle = -3.14159 / 2
        self.sens_angle = 1
        self.wait_change_angle = 0
        self.wait_starting_rot = 0
        self.change_angle = 0
        self.target_angle = -3.14159 / 2

        self.wait_dc = 0
        self.mode_chill = 0

        self.base = np.array([-3.14159 / 2, 0.0, 0.0])
        self.vel = np.array([1.0, 1.0, 1.0])
        self.target = np.array([-3.14159 / 2, 0.0, 0.0])

        self.decay_kick = 0
        self.nrj_slow = 0
        self.nrj_fast = 0

        self.iChannel0 = 0
        self.Prev = 1
        self.Alpha = 2

    def updateParams(self, af):
        if af is None:
            return
        self.time = af["time"] * 0.01
        self.iFrame += 1
        if af["on_kick"]:
            self.mod_fract += 1
            self.go_mnext += 1
            self.go_mnext %= 4
            if self.go_mnext == 0:
                self.next += 1
                self.mnext += 1 * self.sens_m

                if self.mnext > 50:
                    self.sens_m = -1
                if self.mnext < 2:
                    self.sens_m = 1
        self.mod_fract %= self.N_part // 10
        self.next %= self.N_part

        self.mode_chill = af["mini_chill"]

        self.wait_change_angle += 1
        self.wait_starting_rot += 0.005
        if self.wait_change_angle >= 60 * 20 and af["on_kick"]:
            self.target = np.array(self.base) + 2.0 * np.pi * np.sign(
                np.random.rand(3) - 0.5
            )
            self.vel = 0.5 + np.random.rand(3)
            self.wait_change_angle = 0
            self.wait_starting_rot = 0
            self.sens_angle *= -1

            if self.sens_angle == -1:
                self.target_angle = -3.14159 / 2
            else:
                self.target_angle = 2.0 * np.pi - 3.14159 / 2

        if (
            np.linalg.norm(self.target - self.base) < 0.01
            and self.wait_starting_rot > 1.0
        ):
            self.base = np.array([-3.14159 / 2, 0.0, 0.0])
            self.target = self.base
        else:
            tmp = self.target - self.base
            d = np.clip(np.linalg.norm(tmp), 0, 0.3)
            tmp *= d + 1e-6
            self.base = (
                self.base
                + (
                    tmp * af["low"][2] * 0.003
                    + np.sign(self.target - self.base) * 0.008 * af["low"][2]
                )
                * self.vel
            )
            self.wait_change_angle = 0
        self.timeaf = af["time"]
        self.decay_kick = af["decaying_kick"]
        self.nrj_slow = af["low"][1]
        self.nrj_fast = af["smooth_low"]

    def initUniformsBinding(self):
        binding = {
            "modelview": "modelview",
            "projection": "projection",
            "iTime": "timeaf",
            "modNext": "mnext",
            "angle3": "base",
        }
        super().initUniformsBinding(binding, program_name="draw_")
        binding = {
            "modelview": "modelview",
            "projection": "projection",
            "iTime": "timeaf",
            "modNext": "mnext",
            "angle3": "base",
        }
        super().initUniformsBinding(binding, program_name="alpha_")
        binding = {
            "dt": "dt",
            "iTime": "timeaf",
            "iFrame": "iFrame",
            "N_part": "N_part_final",
            "energy_slow": "nrj_slow",
            "energy_fast": "nrj_fast",
            "next": "next",
            "decay_kick": "decay_kick",
            "modNext": "mnext",
            "mod_fract": "mod_fract",
            "mode_chill": "mode_chill",
        }
        super().initUniformsBinding(binding, program_name="transform_")
        binding = {
            "iChannel0": "iChannel0",
            "Prev": "Prev",
            "Alpha": "Alpha",
            "decaying_kick": "decay_kick",
            "mode_chill": "mode_chill",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(
            ["iChannel0", "Prev", "Alpha", "modelview", "projection"]
        )

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="alpha_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="draw_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="transform_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, af):
        self.updateParams(af)
        self.bindUniform(af)

        self.ctx.copy_buffer(self.vbo1, self.vbo2)
        self.transform_vao.transform(self.vbo2, mgl.POINTS, self.N_part)

        self.fbos[0].clear()
        self.fbos[0].use()
        self.ctx.enable(mgl.PROGRAM_POINT_SIZE | mgl.BLEND)
        self.ctx.enable(mgl.DEPTH_TEST)
        self.draw_vao.render(mode=mgl.POINTS)
        self.ctx.disable(mgl.DEPTH_TEST)
        self.ctx.disable(mgl.PROGRAM_POINT_SIZE | mgl.BLEND)

        self.fbos[1].clear()
        self.fbos[1].use()
        self.ctx.enable(mgl.PROGRAM_POINT_SIZE | mgl.BLEND)
        self.ctx.enable(mgl.DEPTH_TEST)
        self.alpha_vao.render(mode=mgl.POINTS)
        self.ctx.disable(mgl.DEPTH_TEST)
        self.ctx.disable(mgl.PROGRAM_POINT_SIZE | mgl.BLEND)

        self.fbos[2], self.fbos[3] = self.fbos[2], self.fbos[3]
        self.fbos[0].color_attachments[0].use(self.iChannel0)
        self.fbos[1].color_attachments[0].use(self.Alpha)
        self.fbos[2].color_attachments[0].use(self.Prev)
        self.fbos[3].use()
        self.vao.render()
        return self.fbos[3].color_attachments[0]

    def norender(self):
        return self.fbos[2].color_attachments[0]


@register_node(OP_CODE_SPIRALPARTICULES)
class SpiralParticulesNode(ShaderNode, Particles):
    op_title = "Spiral Particules"
    op_code = OP_CODE_SPIRALPARTICULES
    content_label = ""
    content_label_objname = "shader_spiral_particules"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = SpiralParticules(ctx=self.scene.ctx, win_size=self.win_size)
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()
        output_texture = self.program.render(audio_features)
        return output_texture
