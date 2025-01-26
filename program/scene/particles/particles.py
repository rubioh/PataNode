from os.path import dirname, join
import glm
import numpy as np

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode
from program.mesh_renderer.renderer import Renderer
from program.mesh_renderer.scene import MeshScene
from program.particles.blender_particles.blender_particles import ParticleSystem

OP_CODE_PARTICLE = name_to_opcode("particle")


@register_program(OP_CODE_PARTICLE)
class Particle(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Particle"
        self.path = "./assets/mesh/spheretiny.glb"
        self.particle_system = ParticleSystem(self.ctx, 1000000)
        self.scene = MeshScene(self.path, ctx, self.particle_system.get_particle_buffer(), self.particle_system.get_particle_buffer_unit_size())
        self.camera = glm.mat4()
        self.projection = glm.perspective(glm.radians(45.0), 16.0 / 9.0, 0.1, 1000.0)
        self.model = glm.mat4()
        self.camera = glm.translate(self.camera, glm.vec3(0, 0., -1.))
       # self.model = glm.scale(self.model, glm.vec3(.01, .01, .01))
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()
        self.load_mesh()
        self.time = 0.

    def load_mesh(self):
        self.scene = MeshScene(self.path, self.ctx, self.particle_system.get_particle_buffer(), self.particle_system.get_particle_buffer_unit_size())
        self.renderer = Renderer(
            self.ctx, self.scene.mesh_resource_manager, self.scene.texture_resource_manager
        )
        self.renderer.add_scene(self.scene)
        self.renderer.add_sun(glm.vec3(0.0, 0., 1.0), glm.vec3(1.))

    def initFBOSpecifications(self):
        self.required_fbos = 2
        fbos_specification = [
            [self.win_size, 4, "f4", True, 3],
            [self.win_size, 4, "f4", False, 1],
        ]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])
            self.fbos_depth_requirement.append(specification[3])
            self.fbos_num_textures.append(specification[4])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "particle.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initUniformsBinding(self):
        binding = {
            "iTime": "time",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms([])

    def initParams(self):
        self.vitesse = 0.4
        self.time = 0

    def getParameters(self):
        return self.adaptableParametersDict

    def updateParams(self, af=None):
        self.time += 0.01 * self.vitesse

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, af=None):
        if not af:
            return
        self.updateParams(af)
        self.particle_system.update()
        self.bindUniform(af)
        self.fbos[0].use()
        self.fbos[0].clear()
        self.renderer.renderGBUFFERinstance(100000, self.particle_system.get_particle_buffer(),
            self.model, self.camera, self.projection, self.fbos[0]
        )
        self.renderer.renderSun(self.fbos[1], self.camera, self.fbos[0])
        return self.fbos[1].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_PARTICLE)
class ParticleNode(ShaderNode, Scene):
    op_title = "Particle"
    op_code = OP_CODE_PARTICLE
    content_label = ""
    content_label_objname = "shader_Particle"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Particle(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()

        return self.program.render(audio_features)
