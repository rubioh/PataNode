import pygltflib
import glm
import numpy as np
from program.mesh_renderer.mesh_resource_manager import MeshResourceManager, TextureResourceManager
from program.mesh_renderer.renderer import render
from program.mesh_renderer.material import Material
from program.mesh_renderer.texture_loader import load_texture_from_gltf

#TODO: separate gltf loading in another file
#TODO: create a retained renderer

class Texture:
	def __init__(self, textureResourceIndex, sampler):
		self.textureResourceIndex = textureResourceIndex
		self.sampler = sampler

	def __str__():
		return str(self.textureResourceIndex + self.sampler)

class Sampler:
	def __init__(self, magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497):
		self.magFilter = magFilter
		self.minFilter = minFilter
		self.wrapS = wrapS
		self.wrapT = wrapT

class Node():
	def __init__(self, transform, meshes, children, name):
		self.transform = transform
		self.children = children
		self.meshes = meshes
		self.name = name
		self.root_nodes = []

	def __str__(self):
		return self.name + "\n"  + "	-transform:"+ str(self.transform)+ "\n" + "	-childs:"+ str(self.children) + "\n" + "	-meshes:"+ str(self.meshes)

class MeshScene():
	def __init__(self, file_path, ctx):
		self.dag = []
		self.mesh_indices = [] #The indices of meshes relative to the gltf scenes
		self.materials = []
		self.samplers = []
		self.textures = [] # Textures as describe by gltf2.0 : a handlers to a image texture and a sampler
		self.texture_resource_indices = [] #The indices of textures relative to the gltf scenes
		self.ctx = ctx
		self.mesh_resource_manager = MeshResourceManager(ctx)
		self.texture_resource_manager = TextureResourceManager(ctx)
		if file_path:
			self.load_scene(file_path)

	def load_transform(self, gltfNode):
		m = glm.mat4()
		rotation = gltfNode.rotation
		translation = gltfNode.translation
		scale = gltfNode.scale

		if gltfNode.translation:
			m = glm.translate(m, translation)

		if gltfNode.rotation:
			m = m * glm.mat4_cast(rotation)

		if gltfNode.scale:
			m[0][0] = scale[0]
			m[1][1] = scale[1]
			m[2][2] = scale[2]

		if gltfNode.matrix:
			m = gltfNode.matrix
		return m

	def load_node(self, gltfNode):
		transform = self.load_transform(gltfNode)
		mesh_resource_indices = []
		for idx in self.mesh_indices[gltfNode.mesh]:
			mesh_resource_indices.append(idx)
		n = Node(transform, mesh_resource_indices, gltfNode.children, gltfNode.name)
		return n

	def load_nodes(self, gltf):
		for node in gltf.nodes:
			self.dag.append(self.load_node(node))

	def convert_accessor_to_list(self, gltf, accessor):
		bufferView = gltf.bufferViews[accessor.bufferView]
		buf = gltf.buffers[bufferView.buffer]
		data = gltf.get_data_from_buffer_uri(buf.uri)
		index = bufferView.byteOffset + accessor.byteOffset
		d = data[index:index+bufferView.byteLength]
		return d
		return np.array(d)

	def load_meshes(self, gltf):
		for mesh in gltf.meshes:
			prim_mesh_indices = []
			for primitive in mesh.primitives:
				accessors = [primitive.attributes.POSITION,
				primitive.attributes.NORMAL, 
				primitive.attributes.TEXCOORD_0,
				primitive.indices,
				primitive.attributes.COLOR_0,
				primitive.attributes.TANGENT]
				buffers = []
				for accessorID in accessors:
					if accessorID is not None:
						accessor = gltf.accessors[accessorID]
						buffers.append(self.convert_accessor_to_list( gltf, accessor) )
					else:
						buffers.append(None)
				indice_type_size = 4

				# if the numbers of indices is < 65535, the component type is gonna be 2 bytes long
				# 5123 is opengl code for unsigned short
				if gltf.accessors[primitive.indices].componentType == 5123:
					indice_type_size = 2
				material = None
				if primitive.material != -1:
					material = self.materials[primitive.material]
				prim_mesh_indices.append(self.mesh_resource_manager.create_mesh(buffers[0], 
					buffers[1], buffers[2], buffers[3], buffers[4], buffers[5], indice_type_size, material))
			self.mesh_indices.append(prim_mesh_indices)

	def load_materials(self, gltf):
		for material in gltf.materials:
			new_material = Material(self.texture_resource_manager)
			new_material.init_from_gltf(gltf, material, self)
			self.materials.append(new_material)

		for m in self.materials:
			print(m)

	def get_texture_resource_index_from_gltf_source(self, gltf, index):
		return self.textures[index]

	def load_textures(self, gltf):
		for sampler in gltf.samplers:
			self.samplers.append(Sampler(sampler.magFilter, sampler.minFilter, sampler.wrapS, sampler.wrapT))

		for image in gltf.images:
			pil_texture = load_texture_from_gltf(gltf, image)
			self.texture_resource_indices.append(
				self.texture_resource_manager.create_texture( (pil_texture[0], pil_texture[1]), pil_texture[2], self.ctx )
				)

		for texture in gltf.textures:
			self.textures.append(Texture(self.texture_resource_indices[texture.source], self.samplers[texture.sampler]))

	def load_scene(self, file_path):
		gltf = pygltflib.GLTF2().load(file_path)
		self.root_nodes = gltf.scenes
		self.load_textures(gltf)
		self.load_materials(gltf)
		self.load_meshes(gltf)
		self.load_nodes(gltf)
		print(gltf)
#		for n in self.dag:
#			print(n)
		del gltf

	def clone(self):
		pass

	def render_node(self, node, matrix, mvp_uniform, surface):
		matrix *= node.transform
		for mesh_rsc_idx in node.meshes:
			mesh = self.mesh_resource_manager.get_resource(mesh_rsc_idx)
			render(matrix, mvp_uniform, surface, mesh, self.ctx, self.mesh_resource_manager, self.texture_resource_manager)
		for child in node.children:
			self.render_node(self.dag[child], matrix, mvp_uniform, surface)

	def render_scene(self, model, view, projection, surface):
		mvp_uniform = {"model": model, "view": view, "projection": projection}
		for scene in self.root_nodes:
			for node_idx in scene.nodes:
				node = self.dag[node_idx]
				self.render_node(node, glm.mat4(), mvp_uniform, surface)