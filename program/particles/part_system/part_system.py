import time
import numpy as np
import cv2
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Effects
from node.node_conf import register_node


OP_CODE_PARTSYSTEM = name_to_opcode('PartSystem')


class PartSystem(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "DoG"

        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        rfbos = 4
        self.required_fbos = rfbos
        fbos_specification = [[self.win_size, 4, 'f4'] for i in range(rfbos)]
        fbos_specification += [
            [(self.N_part, 1), 4, 'f4']
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])


    def initProgram(self, reload=False):
        ### DRAW THINGS
        vert_path = join(dirname(__file__), "draw/draw.vert")
        frag_path = join(dirname(__file__), "draw/draw.frag")
        self.loadProgramToCtx(vert_path, frag_path, reload, name='draw_') 
    
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "draw/final.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name='final_') 

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "draw/trail.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name='trail_') 

        ### Transform
        vert_path = join(dirname(__file__), "transform/transform.vert")
        frag_path = None
        varyings = ["out_pos", "out_col"]
        self.loadProgramToCtx(vert_path, frag_path, reload, name='transform_') 

        ### Colision
        vert_path = join(dirname(__file__), "transform/solve_collision.vert")
        frag_path = None
        varyings = ["out_pos", "out_col"]
        self.loadProgramToCtx(vert_path, frag_path, reload, name='collision_') 

        vert_path = join(dirname(__file__), "transform/copy.vert")
        frag_path = None
        varyings = ["out_pos"]
        self.loadProgramToCtx(vert_path, frag_path, reload, name='copy_') 
    
        self.final_program.program["TrailImg"] = 3
        self.final_program.program["iChannel0"] = 1
        self.final_program.program["iResolution"] = self.win_size
        self.trail_program.program["TrailImg"] = 3
        self.trail_program.program["PartImg"] = 2
        self.trail_program.program["iResolution"] = self.win_size


        # Copy program

        self.vbo1 = self.ctx.buffer(reserve=self.N_part * 28)
        self.vbo2 = self.ctx.buffer(reserve=self.vbo1.size)
        self.vbo_copy = self.ctx.buffer(reserve=self.N_part * 16)

        self.vao_verlet = self.ctx.vertex_array(
            self.part_program, [(self.vbo1, "4f4 3f4", "in_pos", "in_col")]
        )
        self.vao_col = self.ctx.vertex_array(
            self.collision_program, [(self.vbo1, "4f4 3f4", "in_pos", "in_col")]
        )
        self.vao_copy = self.ctx.vertex_array(
            self.copy_program, [(self.vbo1, "4f4 3x4", "in_pos")]
        )

        self.vao = self.ctx.vertex_array(
            self.draw_program, [(self.vbo2, "4f4 3f4", "in_vert", "in_col")]
        )

        self.idx = 0

        self.part_program["dt"] = self.dt
        self.part_program["iResolution"] = self.win_size

        self.target_textures = self.ctx.texture(
            size=(100, 100), components=2, dtype="f4"
        )
        self.target_textures.write(target(self.N_part))

    def init_idx_programs(self):
        idx_vert = open("program/transition/PartSystem/Idx/idx.vert", "r").read()
        idx_frag = open("program/transition/PartSystem/Idx/idx.frag", "r").read()
        self.idx_program = self.ctx.program(
            vertex_shader=idx_vert, fragment_shader=idx_frag, varyings=["pos", "ID"]
        )

        self.idx_texture = self.ctx.texture(
            size=self.win_size, components=4, dtype="f4"
        )
        self.idx_fbo = self.ctx.framebuffer(color_attachments=self.idx_texture)

        self.vao_idx = self.ctx.vertex_array(
            self.idx_program, [(self.vbo2, "4f4 3x4", "in_vert")]
        )

        win2 = (self.win_size[0] * 2, self.win_size[1] * 2)
        tile_frag = "program/transition/PartSystem/Idx/tile.frag"
        self.tile_program = VertFragBase(
            vert_path=None, frag_path=tile_frag, win_size=win2, **self.kwargs
        )
        self.tile_texture = self.ctx.texture(size=win2, components=4, dtype="f4")

        self.idx_texture.filter == (mgl.NEAREST, mgl.NEAREST)
        self.idx_texture.repeat_x = False
        self.idx_texture.repeat_y = False

        self.tile_fbo = self.ctx.framebuffer(color_attachments=self.tile_texture)
        self.vao_tile = self.tile_program.vao

        indices_vert = open(
            "program/transition/PartSystem/Idx/get_indices.vert", "r"
        ).read()
        self.indices_program = self.ctx.program(
            vertex_shader=indices_vert, varyings=["out_vert", "out_col"]
        )
        self.vao_indices = self.ctx.vertex_array(
            self.indices_program, [(self.vbo2, "4f4 3f4", "in_vert", "in_col")]
        )

    def init_params(self):
        super().init_params()
        self.dt = 0.1
        self.N_part = 2000
        self.ps = 12
        self.part_size = 1
        self.iFrame = -5
        self.kick_boom = 0
        self.gravity = (0.0, 0.1)
        self.wait = 0
        self.wait2 = 0

        self.wait_trail = 0
        self.wait_final = 0

    def update_params_on_nothing(self, af):
        if not self.on_in_transition and not self.on_out_transition:
            pass

    def update_params(self, af):
        kick_boom = (np.clip(af["low"][3] - af["low"][2], 0, 1)) * 5 + 1
        self.kick_boom = 0.8 * self.kick_boom + 0.2 * kick_boom
        self.part_size = 4.0 * self.kick_boom**2 + self.ps
        # self.part_size = self.ps
        self.iFrame += 1
        self.gravity = (0.0, -0.00)

    def get_uniform(self, af):
        super().get_uniform(af)
        self.collision_program["part_radius"] = self.part_size / self.win_size[0]
        try:
            self.collision_program["particles"] = 10
        except:
            pass
        try:
            self.collision_program["N"] = self.N_part
        except:
            pass
        try:
            self.collision_program["part_size"] = self.part_size
            self.collision_program["TileIdx"] = 6
        except:
            pass
        self.collision_program["iResolution"] = self.win_size

        self.part_program["gravity"] = self.gravity
        self.part_program["iChannel0"] = 1
        self.part_program["iFrame"] = self.iFrame
        self.part_program["on_kick"] = af["on_kick"]
        self.part_program["part_size"] = self.part_size
        self.part_program["pos_target"] = 8
        # self.draw_program['part_radius'] = self.part_size/self.win_size[0]
        self.tile_program.program["part_radius"] = self.part_size
        self.tile_program.program["iResolution"] = self.win_size
        self.tile_program.program["IdxBuffer"] = 5

        self.final_program.program["wait_final"] = self.wait_final
        self.trail_program.program["wait_trail"] = self.wait_trail

        self.indices_program["iResolution"] = self.win_size
        self.indices_program["TileIdx"] = 6
        self.indices_program["part_size"] = self.part_size
        self.indices_program["part_radius"] = self.part_size / self.win_size[0]
        try:
            self.draw_program["part_size"] = self.part_size
            self.draw_program["iResolution"] = self.win_size
            self.draw_program["image"] = 1
        except:
            pass

    def render(self, texture, af):
        self.update_params(af)
        self.get_uniform(af)

        texture.use(1)
        self.target_textures.use(8)
        self.vao_verlet.transform(self.vbo2, mgl.POINTS, self.N_part)
        self.ctx.copy_buffer(self.vbo1, self.vbo2)

        for i in range(4):
            # self.vao_copy.transform(self.vbo_copy, mgl.POINTS, self.N_part)

            # self.particles.write(self.vbo_copy)

            none = -10
            self.idx_fbo.clear(none, none, none, none)
            self.ctx.point_size = self.part_size
            self.idx_fbo.use()
            self.vao_idx.render(mgl.POINTS, self.N_part)

            # self.tile_fbo.clear(-1,-1,-1,-1)
            # self.idx_fbo.color_attachments[0].use(5)
            # self.tile_fbo.use()
            # self.vao_tile.render()

            # self.particles.use(10)
            self.idx_fbo.color_attachments[0].use(6)
            self.vao_col.transform(self.vbo2, mgl.POINTS, self.N_part)

            self.ctx.copy_buffer(self.vbo1, self.vbo2)

        self.img_fbo.clear(0.0, 0.0, 0.0)
        # self.ctx.point_size = np.clip(self.part_size*2, 0, 200)
        self.ctx.point_size = self.part_size
        # self.ctx.enable(mgl.PROGRAM_POINT_SIZE)
        self.ctx.enable(mgl.BLEND)
        texture.use(1)
        self.img_fbo.use()
        self.vao.render(mgl.POINTS, self.N_part)
        self.ctx.disable(mgl.BLEND)

        self.fbo_trail_2.color_attachments[0].use(3)
        self.img_fbo.color_attachments[0].use(2)
        self.fbo_trail_1.use()
        self.trail_vao.render()
        self.fbo_trail_1, self.fbo_trail_2 = self.fbo_trail_2, self.fbo_trail_1

        self.fbo_trail_1.color_attachments[0].use(3)
        texture.use(1)
        self.render_vao(self.final_vao)




def particle(ID):
    x = np.random.rand(1) * 2 - 1
    y = np.random.rand(1) * 2 - 1

    z = np.random.rand(1) * 2 - 1
    w = np.random.rand(1) * 2 - 1
    return (
        np.array(
            [
                # Position
                x,
                y,  # Vec2
                # Position Last
                x + z * 0.01,
                y + w * 0.01,  # Vec2
                # ID
                # float(ID), # Float
                0.0,
                0.0,
                0.0,
            ]
        )
        .astype("f4")
        .tobytes()
    )


def target(N_paritcules):
    x = np.arange(0, 100).reshape(-1, 1) * 1.0
    y = np.arange(0, 100).reshape(1, -1) * 1.0
    x /= 100
    y /= 100
    x -= 0.5
    y -= 0.5
    x *= 1.5
    y *= 1.5
    res = np.ones((100, 100, 2))
    res[:, :, 0] = x
    res[:, :, 1] = y
    return res.astype("f4").tobytes()

