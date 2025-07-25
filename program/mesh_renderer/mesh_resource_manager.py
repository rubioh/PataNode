from program.mesh_renderer.shaders.shader_builder import build_shaders


class Mesh:
    def __init__(
        self,
        vertex_position,
        vertex_normal,
        vertex_tcs,
        indice_buffer,
        vertex_color,
        vertex_tangent,
        program,
        program_instance,
        ctx,
        idx_size,
        material,
        instance_buffer=None,
        instance_buffer_layout=None,
    ):
        self.ctx = ctx
        self.vbo_position = self.ctx.buffer(vertex_position)

        #       if vertex_normal:
        #           tangent = compute_tangent(indice_buffer, vertex_tcs, vertex_normal, vertex_position, idx_size)
        #
        if vertex_normal:
            self.vbo_normal = self.ctx.buffer(vertex_normal)

        if vertex_tcs:
            self.vbo_tcs = self.ctx.buffer(vertex_tcs)

        if vertex_color:
            self.vbo_color = self.ctx.buffer(vertex_color)

        if vertex_tangent:
            self.vbo_tangent = self.ctx.buffer(vertex_tangent)

        self.vbo_indices = self.ctx.buffer(indice_buffer)

        layout = [(self.vbo_position, "3f", "in_position")]

        if vertex_normal:
            layout.append((self.vbo_normal, "3f", "in_normal"))

        if vertex_tcs:
            layout.append((self.vbo_tcs, "2f", "in_tc"))

        if vertex_color:
            layout.append((self.vbo_color, "3f", "in_color"))

        if vertex_tangent:
            layout.append((self.vbo_tangent, "3f", "in_tangent"))

        self.vao = self.ctx.vertex_array(
            program, layout, index_buffer=self.vbo_indices, index_element_size=idx_size
        )
        if instance_buffer is not None:
            layout.append(
                (instance_buffer, instance_buffer_layout, "in_particle_position")
            )
            self.vao_instance = self.ctx.vertex_array(
                program_instance,
                layout,
                index_buffer=self.vbo_indices,
                index_element_size=idx_size,
            )
        self.program = program
        self.program_instance = program_instance
        self.material = material


class MeshResourceManager:
    def __init__(self, ctx):
        self.ctx = ctx
        self.resources = []

    def get_resource(self, index):
        return self.resources[index]

    def create_mesh(
        self,
        vertex_position,
        vertex_normal,
        vertex_tcs,
        indice_buffer,
        vertex_color,
        vertex_tangent,
        idx_size,
        material,
        program=None,
        instance_buffer=None,
        instance_buffer_layout=None,
    ):
        mesh_layout = {
            "vertex_normal": vertex_normal is not None,
            "vertex_color": vertex_color is not None,
            "vertex_tcs": vertex_tcs is not None,
            "vertex_tangent": vertex_tangent is not None,
        }

        if not program:
            program = self.load_program(mesh_layout, material)
            program_instance = self.load_instance_program(mesh_layout, material)

        mesh = Mesh(
            vertex_position,
            vertex_normal,
            vertex_tcs,
            indice_buffer,
            vertex_color,
            vertex_tangent,
            program,
            program_instance,
            self.ctx,
            idx_size,
            material,
            instance_buffer,
            instance_buffer_layout,
        )

        self.resources.append(mesh)
        return len(self.resources) - 1

    def load_program(self, mesh_layout, material):
        self.code_version = "#version "
        self.code_version += str(3) + str(3) + str("0 core\n")
        vertex_code, fragment_code = build_shaders(mesh_layout, material, False)
        self.vertex_code = self.code_version + vertex_code
        self.fragment_code = self.code_version + fragment_code
        program = self.ctx.program(
            vertex_shader=self.vertex_code, fragment_shader=self.fragment_code
        )
        return program

    def load_instance_program(self, mesh_layout, material):
        self.code_version = "#version "
        self.code_version += str(3) + str(3) + str("0 core\n")
        vertex_code, fragment_code = build_shaders(mesh_layout, material, True)
        self.vertex_code = self.code_version + vertex_code
        self.fragment_code = self.code_version + fragment_code
        program = self.ctx.program(
            vertex_shader=self.vertex_code, fragment_shader=self.fragment_code
        )
        return program


class GPUTexture:
    def __init__(self, resolution, data, ctx, in_components=3, in_dtype="f1"):
        self.resolution = resolution
        self.ctx = ctx
        self.gpu_texture = self.ctx.texture(
            resolution, components=in_components, dtype=in_dtype, data=data
        )

    def bind(self, sampler, location):
        self.gpu_texture.use(location)


class TextureResourceManager:
    def __init__(self, ctx):
        self.ctx = ctx
        self.resources = []

    def get_resource(self, index):
        return self.resources[index]

    def create_texture(self, resolution, data, ctx, in_components=3, in_dtype="f1"):
        self.resources.append(
            GPUTexture(resolution, data, self.ctx, in_components, in_dtype)
        )
        return len(self.resources) - 1
