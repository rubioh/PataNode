import time

import glm
import numpy as np

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Scene
from program.mesh_renderer.renderer import Renderer
from program.mesh_renderer.scene import MeshScene
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_DOME = name_to_opcode("dome")


@register_program(OP_CODE_DOME)
class Dome(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Dome"
        self.ctx = ctx
        self.path = "./assets/mesh/dome.glb"
        self.scene = MeshScene(self.path, ctx)
        self.x = 0.
        self.y = 0.
        self.z = 0.
        self.rx = 0.
        self.ry = 0.
        self.rz = 0.
        self.initProgram()
        self.initFBOSpecifications()
        self.initParams()
        self.initUniformsBinding()
        self.load_mesh()

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
        frag_path = join(dirname(__file__), "dome.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.time = 0
        self.camera = glm.mat4()
#        self.camera = glm.translate(self.camera, glm.vec3(0.0, -10.0, -2.1))
#       self.camera = glm.translate(self.camera, glm.vec3(0., 10., -2.1))
#        self.camera = glm.rotate(self.camera, .3, glm.vec3(1., 0., 0.))
        self.projection = glm.perspective(glm.radians(45.0), 16.0 / 9.0, 0.1, 1000.0)
        self.model = glm.mat4()
        self.model = glm.scale(self.model, glm.vec3(1.0, 1.0, 1.0))
        self.vitesse = 0.4
        self.offset = 0
        self.intensity = 5
        self.smooth_fast = 0
        self.time = 0
        self.tf = 0
        self.eslow = 0.4
        self.emid = 0.2

        self.smooth_fast_final = self.smooth_fast / 2.0
        self.scale_final = 16 + 8 * np.cos(time.time() * 0.1)

    def load_mesh(self):
        self.scene = MeshScene(self.path, self.ctx)
        self.renderer = Renderer(
            self.ctx, self.scene.mesh_resource_manager, self.scene.texture_resource_manager
        )
        self.renderer.add_scene(self.scene)
        self.renderer.add_sun(glm.vec3(1.0, .3, 0.0), glm.vec3(1.0))
    def initUniformsBinding(self):

        binding = {
            "iTime": "time",
            "energy_fast": "smooth_fast_final",
            "energy_slow": "eslow",
            "energy_mid": "emid",
            "tf": "tf",
            "intensity": "intensity",
            "scale": "scale_final",
        }
        self.add_text_edit_cpu_adaptable_parameter("object_path", self.path, self.load_mesh)
        self.add_text_edit_cpu_adaptable_parameter("x", self.x, lambda: 0)
        self.add_text_edit_cpu_adaptable_parameter("y", self.y, lambda: 0)
        self.add_text_edit_cpu_adaptable_parameter("z", self.z, lambda: 0)
        self.add_text_edit_cpu_adaptable_parameter("rx", self.rx, lambda: 0)
        self.add_text_edit_cpu_adaptable_parameter("ry", self.ry, lambda: 0)
        self.add_text_edit_cpu_adaptable_parameter("rz", self.rz, lambda: 0)
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def updateParams(self, af=None):
        v = self.getCpuAdaptableParameters()["program"]["object_path"]["eval_function"]["value"]
        self.x = float(self.getCpuAdaptableParameters()["program"]["x"]["eval_function"]["value"])
        self.y = float(self.getCpuAdaptableParameters()["program"]["y"]["eval_function"]["value"])
        self.z = float(self.getCpuAdaptableParameters()["program"]["z"]["eval_function"]["value"])
        self.rx = float(self.getCpuAdaptableParameters()["program"]["rx"]["eval_function"]["value"])
        self.ry = float(self.getCpuAdaptableParameters()["program"]["ry"]["eval_function"]["value"])
        self.rz = float(self.getCpuAdaptableParameters()["program"]["rz"]["eval_function"]["value"])

        if self.path != v:
            self.path = v
            self.load_mesh()
        self.model = glm.rotate(self.model, 0.002, glm.vec3(1.0, 0.0, 0.0))
        self.vitesse = np.clip(self.vitesse, 0, 2)
        self.intensity = np.clip(self.intensity, 2, 10)
        self.time += 1 / 60 * (1 + self.vitesse)
        self.tf += 0.01

        if af is None:
            return

        self.smooth_fast = self.smooth_fast * 0.2 + 0.8 * af["full"][3]

        if af["full"][1] < 1.0 or af["full"][2] < 0.7:
            self.vitesse += 0.01
            self.intensity += 0.05

            if self.time > 500 and self.vitesse > 1.5:
                self.time = 0
                self.tf = 0
        else:
            self.vitesse -= 0.04
            self.intensity -= 0.1

        self.vitesse = np.clip(self.vitesse, 0, 2)
        self.intensity = np.clip(self.intensity, 2, 10)
        self.time += 1 / 60 * (1 + self.vitesse)
        self.tf += 0.01
        self.eslow = af["full"][1] * 0.75
        self.emid = af["low"][2] / 2.0

        self.smooth_fast_final = self.smooth_fast / 2.0
        self.scale_final = 16 + 8 * np.cos(time.time() * 0.1)

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.fbos[0].use()
        self.fbos[0].clear()
        #self.vao.render()
        camera = glm.mat4()
        camera = glm.translate(camera, glm.vec3(self.x, self.y, self.z))
       # camera = glm.rotate(self.camera, self.rx, glm.vec3(1., 0., 0.))
       # camera = glm.rotate(self.camera, self.ry, glm.vec3(0., 1., 0.))
       # camera = glm.rotate(self.camera, self.rz, glm.vec3(0., 0., 1.))
        self.renderer.renderGBUFFER(
            self.model, camera, self.projection, self.fbos[0]
        )
        self.renderer.renderSun(self.fbos[1], self.camera, self.fbos[0])
        return self.fbos[1].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_DOME)
class DomeNode(ShaderNode, Scene):
    op_title = "Dome"
    op_code = OP_CODE_DOME
    content_label = ""
    content_label_objname = "shader_dome"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = Dome(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            output_texture = self.program.norender()
        else:
            output_texture = self.program.render(audio_features)

        return output_texture
