import moderngl as mgl
import numpy as np

class Mesh():
	def __init__(self, vertex_position, vertex_normal, vertex_tcs, indice_buffer, vertex_color, program, ctx, idx_size):
		self.ctx = ctx
		self.t = "ntm"
		self.vbo_position = self.ctx.buffer(vertex_position)
		self.vbo_normal = self.ctx.buffer(vertex_normal)
		self.vbo_tcs = self.ctx.buffer(vertex_tcs)
		self.vbo_color = self.ctx.buffer(vertex_color)
		self.vbo_indices = self.ctx.buffer(indice_buffer)
		self.uniform = {}
		self.vao = self.ctx.vertex_array(program, 
			[(self.vbo_position, "3f", "in_position"), 
			(self.vbo_normal, "3f", "in_normal"),
			(self.vbo_tcs, "2f", "in_tc"),
			(self.vbo_color, "3f", "in_color")], 
			index_buffer = self.vbo_indices, 
			index_element_size=idx_size)
		self.program = program
		self.material = None

class MeshResourceManager():

	def __init__(self, ctx):
		self.ctx = ctx
		self.resource = []
	
	def get_resource(self, index):
		return self.resource[index]

	def create_mesh(self, vertex_position, vertex_normal, 
		vertex_tcs, indice_buffer, vertex_color, idx_size, program=None):
		if not program:
			program = self.load_program()

		mesh = Mesh(vertex_position, vertex_normal, 
			vertex_tcs, indice_buffer, vertex_color, program, self.ctx, idx_size)
		self.resource.append(mesh);
		return len(self.resource) - 1

	def load_program(self):
		self.code_version = "#version "
		self.code_version += (
			str(3) + str(3) + str("0 core\n")
		)
		with open("./program/mesh_renderer/shaders/vertex_base.glsl") as file:
			self.vertex_code = self.code_version + file.read()
		with open("./program/mesh_renderer/shaders/fragment_base.glsl") as file:
			self.fragment_code = self.code_version + file.read()
		program = self.ctx.program(
			vertex_shader=self.vertex_code, fragment_shader=self.fragment_code
		)
		return program



