import pygltflib
import glm
import numpy as np
from program.mesh_renderer.mesh_resource_manager import MeshResourceManager
from program.mesh_renderer.renderer import render

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
		self.mesh_indices = []
		self.ctx = ctx
		self.mesh_resource_manager = MeshResourceManager(ctx)
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
		n = Node(transform, gltfNode.mesh, gltfNode.children, gltfNode.name)
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
				primitive.attributes.COLOR_0]
				buffers = []
				for accessorID in accessors:
					if accessorID is not None:
						accessor = gltf.accessors[accessorID]
						buffers.append(self.convert_accessor_to_list( gltf, accessor) )
					else:
						buffers.append(np.zeros(1))
				indice_type_size = 4

				# if the numbers of indices is < 65535, the component type is gonna be 2 bytes long
				# 5123 is opengl code for unsigned short
				if gltf.accessors[primitive.indices].componentType == 5123:
					indice_type_size = 2
				prim_mesh_indices.append(self.mesh_resource_manager.create_mesh(buffers[0], 
					buffers[1], buffers[2], buffers[3], buffers[4], indice_type_size))
			self.mesh_indices.append(prim_mesh_indices)

	def load_scene(self, file_path):
		gltf = pygltflib.GLTF2().load(file_path)
		self.root_nodes = gltf.scenes
		self.load_meshes(gltf)
		self.load_nodes(gltf)
#		for n in self.dag:
#			print(n)
		del gltf

	def clone(self):
		pass

	def render_node(self, node, matrix, mvp_uniform, surface):
		matrix *= node.transform
		if node.meshes is not None:
			meshes_idxs = self.mesh_indices[node.meshes]
			for mesh_rsc_idx in meshes_idxs:
				mesh = self.mesh_resource_manager.get_resource(mesh_rsc_idx)
				render(matrix, mvp_uniform, surface, mesh, self.ctx)
		for child in node.children:
			self.render_node(self.dag[child], matrix, mvp_uniform, surface)

	def render_scene(self, model, view, projection, surface):
		mvp_uniform = {"model": model, "view": view, "projection": projection}
		for scene in self.root_nodes:
			for node_idx in scene.nodes:
				node = self.dag[node_idx]
				self.render_node(node, glm.mat4(), mvp_uniform, surface)