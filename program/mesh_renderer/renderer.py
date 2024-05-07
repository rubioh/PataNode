import moderngl as mgl
import numpy as np

def render(transform, mvp_uniform, surface, mesh, ctx):
	program = mesh.program
	surface.use()
	ctx.front_face = 'ccw'
	ctx.enable(mgl.DEPTH_TEST)
	ctx.enable(ctx.CULL_FACE)
	program["model_transform"] = np.array(transform).reshape(1, 16)[0] 
	for k, v in mvp_uniform.items():
		mesh.program[k] = np.array(v).reshape(1, 16)[0]
	for k, v in mesh.uniform.items():
		mesh.program[k] = np.array(v).reshape(1, 16)[0]
	mesh.vao.render(4)
	ctx.disable(ctx.CULL_FACE)
	ctx.disable(mgl.DEPTH_TEST)