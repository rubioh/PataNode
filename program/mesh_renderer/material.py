import glm


class Material:
    def __init__(self, texture_resource_manager):
        self.uniforms = {}
        self.textures = {}
        # 		self.textures["baseColorTexture"] = None
        # 		self.textures["normalTexture"] = None
        # 		self.textures["metallicRoughnessTexture"] = None
        # 		self.textures["emissiveTexture"] = None
        self.uniforms["in_albedo"] = glm.vec4(1.0, 1.0, 1, 0.0)
        self.uniforms["in_metallic"] = 0.0
        self.uniforms["in_roughness"] = 0.5
        self.uniforms["in_emissive"] = glm.vec4(0.0, 0.0, 0.0, 0.0)
        self.name = "uninitialized"
        self.texture_resource_manager = texture_resource_manager

    def init_from_gltf(self, gltf, pygltf_material, scene):
        mat = pygltf_material.pbrMetallicRoughness
        self.uniforms["in_albedo"] = mat.baseColorFactor
        self.uniforms["in_metallic"] = mat.metallicFactor
        self.uniforms["in_roughness"] = mat.roughnessFactor
        self.uniforms["in_emissive"] = pygltf_material.emissiveFactor
        self.name = pygltf_material.name

        if mat.baseColorTexture:
            self.textures["baseColorTexture"] = (
                scene.get_texture_resource_index_from_gltf_source(
                    gltf, mat.baseColorTexture.index
                )
            )

        if mat.metallicRoughnessTexture:
            self.uniforms["in_metallic"] = 1.0
            self.uniforms["in_roughness"] = 0.0
            self.textures["metallicRoughnessTexture"] = (
                scene.get_texture_resource_index_from_gltf_source(
                    gltf, mat.metallicRoughnessTexture.index
                )
            )

        if pygltf_material.normalTexture:
            self.textures["normalTexture"] = (
                scene.get_texture_resource_index_from_gltf_source(
                    gltf, pygltf_material.normalTexture.index
                )
            )

    # TODO: COMPUTE TANGENT BITANGENT

    def set_uniform(self, key, value):
        self.uniforms[key] = value
