import moderngl as mgl
import numpy as np
import glm
#class RenderNode:
#	def __init__(self):
#		self.meshes = []
#		self.transform = glm.mat4()
#
#class Dag:
#	def __init__(self, scene):
#		pass
#
#class Renderer:

#	def __init__(self, ctx, MeshResourceManager, TextureResourceManager):

def render(transform, mvp_uniform, surface, mesh, ctx, mesh_resource_manager, texture_resource_manager):
	program = mesh.program
	material = mesh.material
	surface.use()
	ctx.front_face = 'ccw'
	ctx.enable(mgl.DEPTH_TEST)
	ctx.enable(ctx.CULL_FACE)
	program["model_transform"] = np.array(transform).reshape(1, 16)[0] 
	for k, v in mvp_uniform.items():
		mesh.program[k] = np.array(v).reshape(1, 16)[0]
	for k, v in material.uniforms.items():
#		print(k, v)
		# Scalar value dont need to be reshaped, vec3 are automatically cast to vec4
		if isinstance(v, float) or isinstance(v, int):
			mesh.program[k] = float(v)
		else:
			value = v
			if len(value) == 3:
				value = glm.vec4(v[0], v[1],v[2], 0.)
			mesh.program[k] = np.array(value).reshape(1, len(value))[0]
	location = 0
	for texture_name, texture in material.textures.items():
		gputexture = texture_resource_manager.get_resource(texture.textureResourceIndex)
		gputexture.bind(texture.sampler, location)
#		mesh.program[texture_name].use(location)
		location = location + 1
#	for k, v in mesh.uniform.items():
#		mesh.program[k] = np.array(v).reshape(1, 16)[0]
	mesh.vao.render(4)
	ctx.disable(ctx.CULL_FACE)
	ctx.disable(mgl.DEPTH_TEST)