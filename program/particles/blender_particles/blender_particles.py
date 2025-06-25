from os.path import dirname, join


def read_file(path):
    f = open(path, "r")
    return f.read()


class ParticleSystem:
    def __init__(self, ctx, num_particle=10000):
        self.ctx = ctx
        self.compute_shader = ctx.compute_shader(
            read_file(join(dirname(__file__), "compute.glsl"))
        )
        self.init_shader = ctx.compute_shader(
            read_file(join(dirname(__file__), "init.glsl"))
        )

        self.iFrame = 0
        # 4 float of 4 bytes (f32)
        self.buffer_size = num_particle * 16
        self.compute_shader_initialized = False
        # group size is 256
        self.num_group = (num_particle // 256) + 1
        self.position_buffer = [
            ctx.buffer(None, self.buffer_size, True),
            ctx.buffer(None, self.buffer_size, True),
        ]
        self.velocity_buffer = [
            ctx.buffer(None, self.buffer_size, True),
            ctx.buffer(None, self.buffer_size, True),
        ]

    def initProgram(self, reload=False):
        vert_path = join(dirname(__file__), "mapping_vertex.glsl")
        frag_path = join(dirname(__file__), "mapping.glsl")
        self.program = self.ctx.program(
            vertex_shader=read_file(vert_path), fragment_shader=read_file(frag_path)
        )

    def load_program(self, mesh_layout, material):
        vert_path = join(dirname(__file__), "mapping_vertex.glsl")
        frag_path = join(dirname(__file__), "mapping.glsl")
        vertex_code = read_file(vert_path)
        fragment_code = read_file(frag_path)

        self.vertex_code = self.code_version + vertex_code
        self.fragment_code = self.code_version + fragment_code
        program = self.ctx.program(
            vertex_shader=self.vertex_code, fragment_shader=self.fragment_code
        )
        return program

    def init_compute(self):
        self.position_buffer[(self.iFrame + 0) % 2].bind_to_storage_buffer(
            0, 0, self.buffer_size
        )
        self.position_buffer[(self.iFrame + 1) % 2].bind_to_storage_buffer(
            2, 0, self.buffer_size
        )
        self.velocity_buffer[(self.iFrame + 0) % 2].bind_to_storage_buffer(
            1, 0, self.buffer_size
        )
        self.velocity_buffer[(self.iFrame + 1) % 2].bind_to_storage_buffer(
            3, 0, self.buffer_size
        )
        self.init_shader.run(self.num_group, 1, 1)
        self.ctx.finish()
        self.compute_shader_initialized = True

    def update(self):
        if not self.compute_shader_initialized:
            self.init_compute()
        self.position_buffer[(self.iFrame + 0) % 2].bind_to_storage_buffer(
            0, 0, self.buffer_size
        )
        self.position_buffer[(self.iFrame + 1) % 2].bind_to_storage_buffer(
            2, 0, self.buffer_size
        )
        self.velocity_buffer[(self.iFrame + 0) % 2].bind_to_storage_buffer(
            1, 0, self.buffer_size
        )
        self.velocity_buffer[(self.iFrame + 1) % 2].bind_to_storage_buffer(
            3, 0, self.buffer_size
        )

        self.compute_shader.run(self.num_group, 1, 1)
        self.ctx.finish()
        self.iFrame = (self.iFrame + 1) % 2

    def get_particle_buffer(self):
        return self.position_buffer[(self.iFrame + 1) % 2]

    def get_particle_buffer_unit_size(self):
        return "4f/i"

    def render():
        pass
