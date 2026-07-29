from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Utils
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, name_to_opcode, register_program

OP_CODE_MOTIONFLOW = name_to_opcode("motionflow")


@register_program(OP_CODE_MOTIONFLOW)
class MotionFlow(ProgramBase):
    def __init__(
        self,
        ctx=None,
        major_version=3,
        minor_version=3,
        win_size=(960, 540),
        downscale=4,
    ):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Motion Flow"

        # Flow is estimated at a fraction of the output resolution: cheaper, and the
        # coarser the grid the larger the per-frame displacement it can still follow.
        # This sizes the FBOs, so it is fixed at construction rather than a uniform.
        self.downscale = max(1, int(downscale))
        self.compute_size = (
            max(1, self.win_size[0] // self.downscale),
            max(1, self.win_size[1] // self.downscale),
        )

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 7

        # 0,1 luminance ping-pong (this frame / last frame)
        # 2,3 flow ping-pong (Lucas-Kanade output, then smoothing iterations)
        # 4,5 accumulation ping-pong (temporal persistence)
        # 6   packed output at full resolution
        fbos_specification = [[self.compute_size, 4, "f4"] for _ in range(6)]
        fbos_specification.append([self.win_size, 4, "f4"])

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH

        frag_path = join(dirname(__file__), "prefilter.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="prefilter_")

        frag_path = join(dirname(__file__), "flow.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="flow_")

        frag_path = join(dirname(__file__), "smooth.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="smooth_")

        frag_path = join(dirname(__file__), "accum.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="accum_")

        frag_path = join(dirname(__file__), "motion_flow.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        # Texture units
        self.iChannel0 = 0
        self.CurrLuma = 1
        self.PrevLuma = 2
        self.FlowTex = 3
        self.AccumTex = 4

        # Loop count, not a uniform: the exposition system carries uniform values.
        self.smooth_iterations = 4

        # Gates the accumulator until a previous frame actually exists.
        self.iFrame = 0
        self.flow_valid = 0.0

        self.flow_gain = 1.0
        self.persistence = 0.85
        self.noise_threshold = 0.002
        self.lambda_reg = 0.05
        self.magnitude_scale = 8.0

    def initUniformsBinding(self):
        # The compute passes run into reduced-size FBOs, so their iResolution is
        # bound to compute_size while the output pass keeps the real one.
        binding = {
            "iResolution": "compute_size",
            "iChannel0": "iChannel0",
        }
        super().initUniformsBinding(binding, program_name="prefilter_")

        binding = {
            "iResolution": "compute_size",
            "CurrLuma": "CurrLuma",
            "PrevLuma": "PrevLuma",
            "lambda_reg": "lambda_reg",
        }
        super().initUniformsBinding(binding, program_name="flow_")

        binding = {
            "iResolution": "compute_size",
            "FlowTex": "FlowTex",
        }
        super().initUniformsBinding(binding, program_name="smooth_")

        binding = {
            "iResolution": "compute_size",
            "FlowTex": "FlowTex",
            "AccumTex": "AccumTex",
            "flow_gain": "flow_gain",
            "persistence": "persistence",
            "noise_threshold": "noise_threshold",
            "flow_valid": "flow_valid",
        }
        super().initUniformsBinding(binding, program_name="accum_")

        binding = {
            "iResolution": "win_size",
            "AccumTex": "AccumTex",
            "magnitude_scale": "magnitude_scale",
        }
        super().initUniformsBinding(binding, program_name="")

        # flow_valid is internal state, not something to hand the user a slider for.
        self.addProtectedUniforms(
            ["iChannel0", "CurrLuma", "PrevLuma", "FlowTex", "AccumTex", "flow_valid"]
        )

    def updateParams(self, af):
        if af is None:
            return

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="prefilter_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="flow_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="smooth_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="accum_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        # Counted here rather than in updateParams, which returns early without audio.
        self.flow_valid = 0.0 if self.iFrame < 1 else 1.0
        self.iFrame += 1

        self.bindUniform(af)
        self.updateParams(af)

        # Prefilter into this frame's luminance buffer. fbos[1] still holds last
        # frame's, which is the whole basis of the estimate.
        textures[0].use(0)
        self.fbos[0].use()
        self.prefilter_vao.render()

        # Lucas-Kanade
        self.fbos[0].color_attachments[0].use(1)
        self.fbos[1].color_attachments[0].use(2)
        self.fbos[2].use()
        self.flow_vao.render()

        # Smoothing iterations, each one widening the region with a usable estimate
        for _ in range(self.smooth_iterations):
            self.fbos[2].color_attachments[0].use(3)
            self.fbos[3].use()
            self.smooth_vao.render()
            self.fbos[2], self.fbos[3] = self.fbos[3], self.fbos[2]

        # Temporal accumulation against the previous field
        self.fbos[2].color_attachments[0].use(3)
        self.fbos[5].color_attachments[0].use(4)
        self.fbos[4].use()
        self.accum_vao.render()
        self.fbos[4], self.fbos[5] = self.fbos[5], self.fbos[4]

        # Pack and upscale to output resolution
        self.fbos[5].color_attachments[0].use(4)
        self.fbos[6].use()
        self.vao.render()

        # This frame's luma becomes next frame's reference
        self.fbos[0], self.fbos[1] = self.fbos[1], self.fbos[0]

        return self.fbos[6].color_attachments[0]

    def norender(self):
        return self.fbos[6].color_attachments[0]


@register_node(OP_CODE_MOTIONFLOW)
class MotionFlowNode(ShaderNode, Utils):
    op_title = "Motion Flow"
    op_code = OP_CODE_MOTIONFLOW
    content_label = ""
    content_label_objname = "shader_motion_flow"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = MotionFlow(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()

        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()

        texture = input_nodes[0].render(audio_features)

        if texture is None:
            return self.program.norender()

        output_texture = self.program.render([texture], audio_features)
        return output_texture
