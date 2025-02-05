import glm
import moderngl as mgl
import numpy as np

from os.path import dirname

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data

#class RenderNode:
#    def __init__(self):
#        self.meshes = []
#        self.transform = glm.mat4()
#
#class Dag:
#    def __init__(self, scene):
#        pass



def read_file(path):
    f = open(path, "r")
    return f.read()


def create_screen_render_pass(path, ctx):
    code_version = "#version "
    code_version += str(3) + str(3) + str("0 core\n")

    vert_path = SQUARE_VERT_PATH
    frag_path = dirname(__file__) + path
    program = ctx.program(
        vertex_shader=read_file(vert_path),
        fragment_shader=code_version + read_file(frag_path),
    )
    vbo = ctx.buffer(get_square_vertex_data())
    vao = ctx.vertex_array(program, [(vbo, "2f", "in_position")])
    return vao, program


class Sun:
    def __init__(self, direction, color):
        self.direction = direction
        self.color = color


class Renderer:
    def create_sun_program(self):
        vao, program = create_screen_render_pass("/shaders/sun.glsl", self.ctx)
        self.sun_vao = vao
        self.sun_program = program

    def __init__(self, ctx, mesh_resource_manager, texture_resource_manager):
        self.mesh_resource_manager = mesh_resource_manager
        self.texture_resource_manager = texture_resource_manager
        self.scenes = []
        self.suns = []
        self.ctx = ctx
        self.create_sun_program()

    def add_sun(self, direction, color):
        self.suns.append(Sun(direction, color))

    def add_scene(self, scene):
        self.scenes.append(scene)
        return len(self.scenes) - 1

    def renderGBUFFER(self, model, view, projection, surface):
        for scene in self.scenes:
            scene.render_scene(model, view, projection, surface)

    def renderGBUFFERinstance(self, num, instance_buffer, model, view, projection, surface):
        for scene in self.scenes:
            scene.render_scene_instance(num, instance_buffer, model, view, projection, surface)

    def renderSun(self, surface, view, gbuffer):
        for sun in self.suns:
            self.sun_program["albedoMetallicTexture"] = 0
            self.sun_program["normalRoughnessTexture"] = 1
            self.sun_program["emissiveTexture"] = 2
            gbuffer.color_attachments[0].use(0)
            gbuffer.color_attachments[1].use(1)
            gbuffer.color_attachments[2].use(2)
            self.sun_program["view"] = np.array(view).reshape(1, 16)[0]
            self.sun_program["lightDir"] = np.array(sun.direction).reshape(1, 3)[0]
            self.sun_program["lightColor"] = np.array(sun.color).reshape(1, 3)[0]
            surface.use()
            self.sun_vao.render(4)

    def renderLighing(self, surface, view):
        self.renderSuns(surface, view)

    def clear(self):
        self.scene = []


#   def remove_scene(self, scene_idx):
#       pass


def render(
    transform,
    mvp_uniform,
    surface,
    mesh,
    ctx,
    mesh_resource_manager,
    texture_resource_manager,
    num_instance = None,
    instance_buffer = None,
):
    if not instance_buffer:
        program = mesh.program
    else:
        program = mesh.program_instance
    material = mesh.material
    surface.use()
    ctx.front_face = "ccw"
    ctx.enable(mgl.DEPTH_TEST)
    ctx.enable(ctx.CULL_FACE)
#   mvp = transform * mvp_uniform["model"] * mvp_uniform["view"] * mvp_uniform["projection"]
    mvp = (
        mvp_uniform["projection"]
        * mvp_uniform["view"]
        * mvp_uniform["model"]
        * transform
    )
    program["model"] = np.array(mvp_uniform["model"] * transform).reshape(1, 16)[0]
    program["mvp"] = np.array(mvp).reshape(1, 16)[0]
#   for k, v in mvp_uniform.items():
#       mesh.program[k] = np.array(v).reshape(1, 16)[0]
    for k, v in material.uniforms.items():
#       print(k, v)

        # Scalar value dont need to be reshaped, vec3 are automatically cast to vec4
        if isinstance(v, float) or isinstance(v, int):
            program[k] = float(v)
        else:
            value = v

            if len(value) == 3:
                value = glm.vec4(v[0], v[1], v[2], 0.0)

            program[k] = np.array(value).reshape(1, len(value))[0]

    location = 0

    for texture_name, texture in material.textures.items():
        gputexture = texture_resource_manager.get_resource(texture.textureResourceIndex)
        program[texture_name] = location
        gputexture.bind(texture.sampler, location)
#       mesh.program[texture_name].use(location)
        location = location + 1
#
#       for k, v in mesh.uniform.items():
#           mesh.program[k] = np.array(v).reshape(1, 16)[0]

    if not instance_buffer:
        mesh.vao.render(4)
    else:
        mesh.vao_instance.render(4, instances=num_instance)

    ctx.disable(ctx.CULL_FACE)
    ctx.disable(mgl.DEPTH_TEST)
