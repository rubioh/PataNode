import moderngl as mgl
import numpy as np
from program.mesh_renderer.shaders.shader_builder import build_shaders

class Mesh():
	def __init__(self, vertex_position, vertex_normal, 
		vertex_tcs, indice_buffer, vertex_color, program, ctx, idx_size, material):
		self.ctx = ctx
		self.vbo_position = self.ctx.buffer(vertex_position)
		self.vbo_normal = self.ctx.buffer(vertex_normal)
		self.vbo_tcs = self.ctx.buffer(vertex_tcs)
		self.vbo_color = self.ctx.buffer(vertex_color)
		self.vbo_indices = self.ctx.buffer(indice_buffer)
		self.vao = self.ctx.vertex_array(program, 
			[(self.vbo_position, "3f", "in_position"), 
			(self.vbo_normal, "3f", "in_normal"),
			(self.vbo_tcs, "2f", "in_tc"),
			(self.vbo_color, "3f", "in_color")], 
			index_buffer = self.vbo_indices, 
			index_element_size=idx_size)
		self.program = program
		self.material = material

class MeshResourceManager():

	def __init__(self, ctx):
		self.ctx = ctx
		self.resource = []

	def get_resource(self, index):
		return self.resource[index]

	def create_mesh(self, vertex_position, vertex_normal, 
		vertex_tcs, indice_buffer, vertex_color, idx_size, material, program=None):

		mesh_layout = { "vertex_normal": vertex_normal != None,
			"vertex_color": vertex_color != None,
			"vertex_tcs": vertex_tcs != None,
			"vertex_bitangent": False#vertex_bitangeant != None,
		}

		if not program:
			program = self.load_program(mesh_layout, material)

		mesh = Mesh(vertex_position, vertex_normal, 
			vertex_tcs, indice_buffer, vertex_color, program, self.ctx, idx_size, material)
		self.resource.append(mesh);
		return len(self.resource) - 1

	def load_program(self, mesh_layout, material):
		self.code_version = "#version "
		self.code_version += (
			str(3) + str(3) + str("0 core\n")
		)
		vertex_code, fragment_code = build_shaders(mesh_layout, material)
		self.vertex_code = self.code_version + vertex_code
		self.fragment_code = self.code_version + fragment_code
		program = self.ctx.program(
			vertex_shader=self.vertex_code, fragment_shader=self.fragment_code
		)
		return program

class GPUTexture:
	def __init__(self, resolution, data, ctx, in_components = 3, in_dtype = "f4"):
		self.resolution = resolution
		self.ctx = ctx
		self.gpu_texture = self.ctx.texture(
			resolution, components=in_components, dtype=in_dtype, data=data
		)

		def Bind(self, sampler, location):
			self.gpu_texture.use(location)

class TextureResourceManager():
	def __init__(self, ctx):
		self.ctx = ctx
		self.resources = []

	def get_resource(self, index):
		return self.resource[index]

	def create_texture(self, resolution, data, ctx, in_components = 3, in_dtype = "f4"):
		self.resources.append(GPUTexture(resolution, data, self.ctx, in_components, in_dtype))