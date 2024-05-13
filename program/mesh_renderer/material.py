import glm
import pygltflib

class Material:
	def __init__(self, texture_resource_manager):
		self.baseColorTexture = None
		self.normalTexture = None
		self.metallicRoughnessTexture = None
		self.emissiveTexture = None
		self.albedo = glm.vec3(1., 1., 1.)
		self.metallicFactor = 0.0
		self.roughnessFactor = 0.5
		self.emissiveFactor = glm.vec3(0., 0., 0.)
		self.name = "uninitialized"
		self.texture_resource_manager = texture_resource_manager

	def init_from_gltf(self, gltf, pygltf_material, scene):
		mat = pygltf_material.pbrMetallicRoughness
		self.albedo = mat.baseColorFactor
		self.metallicFactor = mat.metallicFactor
		self.roughnessFactor = mat.roughnessFactor
		self.emissiveFactor = pygltf_material.emissiveFactor
		self.name = pygltf_material.name
		if mat.baseColorTexture:
			self.baseColorTexture = scene.get_texture_resource_index_from_gltf_source(gltf, mat.baseColorTexture.index)
		if mat.metallicRoughnessTexture:
			self.metallicRoughnessTexture = scene.get_texture_resource_index_from_gltf_source(gltf, mat.metallicRoughnessTexture.index)
	#	if pygltf_material.normalTexture:
	#		self.normalTexture = scene.get_texture_resource_index_from_gltf_source(gltf, pygltf_material.normalTexture.index)
	# TODO COMPUTE TANGENT BITANGENT

	def set_uniforms(self, uniforms):
		self.uniforms = uniforms

	def create_program(self):
		pass

	def __str__(self):
		return "Albedo: "+ str(self.albedo) + "metallicFactor: " + str(self.metallicFactor) + "roughnessFactor: " + str(self.roughnessFactor) + "emissiveFactor: " + str(self.emissiveFactor) + "name: " + str(self.name)


#baseColorTexture=TextureInfo(extensions={}, extras={}, index=0, texCoord=0),
 #metallicRoughnessTexture=None), normalTexture=None,
  #emissiveFactor=[0.0, 0.0, 0.0], emissiveTexture=None, alphaMode='OPAQUE', alphaCutoff=0.5, doubleSided=True, name='Material.002'
