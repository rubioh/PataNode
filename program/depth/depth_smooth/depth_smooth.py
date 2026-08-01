from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import DepthTexture, ShaderNode
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, name_to_opcode, register_program

OP_CODE_DEPTH_SMOOTH = name_to_opcode("DepthSmooth")

# 1.0 is passthrough; lower is smoother and trails more.
DEFAULT_SMOOTH_RATE = 0.25

# Roughly half a second at the camera's 30fps.
DEFAULT_HOLD_FRAMES = 15.0


@register_program(OP_CODE_DEPTH_SMOOTH)
class DepthSmooth(ProgramBase):
    """Temporal smoothing for a depth image.

    Blends each pixel with the previous frame and holds the last valid depth
    while a pixel is unmeasured, so the sensor's flicker and its strobing holes
    both settle. Knows nothing about the camera -- it operates on whatever
    depth-shaped image it is given, so it works against the synthetic source
    too.
    """

    def __init__(
        self,
        ctx=None,
        major_version=3,
        minor_version=3,
        win_size=(960, 540),
    ):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Depth Smooth"

        # Must precede initProgram: uniforms already protected when the shader
        # is parsed get no inspector entry at all. Both are sampler units,
        # bound explicitly in render(), so neither is meaningful to drive from
        # an expression.
        self.addProtectedUniforms(["input_texture", "history"])

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initParams(self):
        self.smooth_rate = DEFAULT_SMOOTH_RATE
        self.hold_frames = DEFAULT_HOLD_FRAMES

        # Which of the two FBOs the next render writes to. The other one holds
        # the previous frame, so the pair swaps roles every frame -- no copy is
        # needed, and reading the buffer being written (undefined in GL) never
        # happens.
        self._write_index = 0
        self._last_output = None
        self._history_cleared = False

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "depth_smooth.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initFBOSpecifications(self):
        # Two: one written this frame, one holding the previous frame.
        self.required_fbos = 2
        fbos_specification = [[self.win_size, 4, "f4"], [self.win_size, 4, "f4"]]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "smooth_rate": "smooth_rate",
            "hold_frames": "hold_frames",
        }
        super().initUniformsBinding(binding, program_name="")

    def connectFbos(self, fbos=None):
        connected = super().connectFbos(fbos)

        # These come from a shared pool and hold whatever the previous owner
        # left in them. Treat them as empty history rather than blending the
        # first frames against a stale image -- and reset the swap, since
        # restoreFBODependencies hands out buffers again from scratch.
        self._write_index = 0
        self._last_output = None
        self._history_cleared = False

        return connected

    def updateParams(self, af=None):
        pass

    def bindUniform(self, af=None):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def norender(self):
        # The buffer written last, not fbos[0]: the two swap every frame.
        if self._last_output is None:
            return self.fbos[0].color_attachments[0]

        return self._last_output

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)

        if not self._history_cleared:
            for fbo in self.fbos:
                fbo.clear(0.0, 0.0, 0.0, 0.0)
            self._history_cleared = True

        output = self.fbos[self._write_index]
        history = self.fbos[1 - self._write_index]

        self.program["input_texture"] = 1
        self.program["history"] = 2
        textures[0].use(1)
        history.color_attachments[0].use(2)

        output.use()
        self.vao.render()

        # Next frame reads what was just written and writes over the buffer
        # that was just read.
        self._write_index = 1 - self._write_index
        self._last_output = output.color_attachments[0]

        return self._last_output


@register_node(OP_CODE_DEPTH_SMOOTH)
class DepthSmoothNode(ShaderNode, DepthTexture):
    op_title = "Depth Smooth"
    op_code = OP_CODE_DEPTH_SMOOTH
    content_label = ""
    content_label_objname = "depth_smooth"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = DepthSmooth(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.already_called:
            return self.program.norender()

        self.already_called = True
        input_nodes = self.getShaderInputs()

        if not len(input_nodes):
            return self.program.norender()

        if input_nodes[0].already_called:
            texture = input_nodes[0].program.norender()
        else:
            texture = input_nodes[0].render(audio_features)

        return self.program.render([texture], audio_features)
