import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import (
    SQUARE_VERT_PATH,
    get_square_vertex_data,
    register_program,
    name_to_opcode,
)
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Utils
from node.node_conf import register_node


OP_CODE_FLUID = name_to_opcode("fluid")


@register_program(OP_CODE_FLUID)
class Fluid(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Fluid"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        rfbo = 6
        self.required_fbos = rfbo
        fbos_specification = [[self.win_size, 4, "f4"] for i in range(rfbo)]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "ADF/advect.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="adf_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Ink/ink.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="ink_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Jacobi/jacobid.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="jacd_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Jacobi/jacobip.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="jacp_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "SubPressure/subpressure.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="subpressure_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "fluid.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.iChannel0 = 0
        self.FieldState = 1
        self.InkState = 2
        self.VelocityInput = 3
        self.FieldStateSP = 4

        self.vort_amount = 0.1
        self.dt = 0.2
        self.advect_amount = 3.0  # Advect amount
        self.decay_rate = 0.9
        self.kappa = 4.0  # Diffusion amount
        self.iFrame = -1
        self.on_kick = 0
        self.passthrough = 0.0
        self.input_vel_intensity = 10.0
        self.input_vel_intensity_passthrough = 0.01

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "FieldState": "FieldState",
            "VelocityState": "VelocityInput",
            "dt": "dt",
            "advect_amount": "advect_amount",
            "gate_open": "on_kick",
            "input_vel_intensity": "input_vel_intensity",
            "input_vel_intensity_passthrough": "input_vel_intensity_passthrough",
        }
        super().initUniformsBinding(binding, program_name="adf_")
        binding = {
            "iResolution": "win_size",
            "iFrame": "iFrame",
            "FieldState": "FieldState",
            "InkState": "InkState",
            "iChannel0": "iChannel0",
            "dt": "dt",
            "advect_amount": "advect_amount",
            "gate_open": "on_kick",
            "decay_rate": "decay_rate",
            "passthrough": "passthrough",
        }
        super().initUniformsBinding(binding, program_name="ink_")
        binding = {
            "iResolution": "win_size",
            "FieldState": "FieldState",
            "dt": "dt",
            "kappa": "kappa",
        }
        super().initUniformsBinding(binding, program_name="jacd_")
        binding = {
            "iResolution": "win_size",
            "FieldState": "FieldState",
        }
        super().initUniformsBinding(binding, program_name="jacp_")
        binding = {
            "iResolution": "win_size",
            "FieldStateSP": "FieldStateSP",
            "vort_amount": "vort_amount",
        }
        super().initUniformsBinding(binding, program_name="subpressure_")
        binding = {
            "iResolution": "win_size",
            "InkState": "InkState",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(
            ["iChannel0", "FieldState", "InkState", "VelocityState", "FieldStateSP"]
        )

    def updateParams(self, af):
        if af is None:
            return
        self.iFrame += 1
        self.on_kick = af["on_kick"]

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="ink_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="adf_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="jacp_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="jacd_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="subpressure_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.bindUniform(af)
        self.updateParams(af)

        ink_input = textures[0]
        vel_input = textures[1]

        # Ink Texture
        # texture.use(21)
        self.fbos[2].color_attachments[0].use(1)
        self.fbos[1].color_attachments[0].use(2)
        ink_input.use(0)
        self.fbos[0].use()
        self.ink_vao.render()
        self.fbos[0], self.fbos[1] = self.fbos[1], self.fbos[0]

        # Advect
        self.fbos[2].color_attachments[0].use(1)
        vel_input.use(3)
        self.fbos[3].use()
        self.adf_vao.render()

        # Diffuse
        for i in range(4):
            self.fbos[3].color_attachments[0].use(1)
            self.fbos[2].use()
            self.jacd_vao.render()
            self.fbos[2], self.fbos[3] = self.fbos[3], self.fbos[2]

        # Get pressure
        for i in range(4):
            self.fbos[3].color_attachments[0].use(1)
            self.fbos[2].use()
            self.jacd_vao.render()
            self.fbos[2], self.fbos[3] = self.fbos[3], self.fbos[2]

        # Divergence free
        self.fbos[3].color_attachments[0].use(4)
        self.fbos[2].use()
        self.subpressure_vao.render()

        self.fbos[0].color_attachments[0].use(2)
        self.fbos[5].use()
        self.vao.render()
        return self.fbos[5].color_attachments[0]

    def norender(self):
        return self.fbos[5].color_attachments[0]


@register_node(OP_CODE_FLUID)
class FluidNode(ShaderNode, Utils):
    op_title = "Fluid"
    op_code = OP_CODE_FLUID
    content_label = ""
    content_label_objname = "shader_fluid"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1, 2], outputs=[3])
        self.program = Fluid(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()
        input_nodes = self.getShaderInputs()
        if len(input_nodes) < 2:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        vel = input_nodes[1].render(audio_features)
        if texture is None or vel is None:
            return self.program.norender()
        output_texture = self.program.render([texture, vel], audio_features)
        return output_texture
