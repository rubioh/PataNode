from os.path import dirname, join

import moderngl
import numpy as np

from depth.depth_engine import NO_FRAME_ID
from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Texture
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, name_to_opcode, register_program

OP_CODE_DEPTH_INPUT = name_to_opcode("DepthInput")

DEFAULT_NEAR_MM = 500.0
DEFAULT_FAR_MM = 4000.0


@register_program(OP_CODE_DEPTH_INPUT)
class DepthInput(ProgramBase):
    """Uploads depth frames from the DepthEngine and normalises them in GLSL.

    Deliberately knows nothing about threads or the camera SDK: it pulls
    whatever the engine last published and blits it.
    """

    def __init__(
        self,
        ctx=None,
        major_version=3,
        minor_version=3,
        win_size=(960, 540),
        engine=None,
    ):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Depth Input"
        self.engine = engine

        self._last_frame_id = NO_FRAME_ID
        self._depth_scale = 1.0

        # Order matters: initProgram sets self.name, which initUniformsBinding
        # needs to key its parameter dict. Matches program/scene/texture.
        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

    def initParams(self):
        # A 1x1 zero texture so the shader always has something bindable, even
        # before the first frame -- or forever, if no camera ever appears. Raw 0
        # already means "unmeasured", so "no camera" and "hole" collapse into
        # the same transparent output instead of two cases downstream.
        self.depth_texture = self.ctx.texture((1, 1), components=1, dtype="u2")
        self.depth_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.depth_texture.write(np.zeros((1, 1), dtype=np.uint16))

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "depth_input.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [[self.win_size, 4, "f4"]]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initUniformsBinding(self):
        binding = {}
        self.add_float_cpu_adaptable_parameter("near_mm", DEFAULT_NEAR_MM)
        self.add_float_cpu_adaptable_parameter("far_mm", DEFAULT_FAR_MM)
        self.add_float_cpu_adaptable_parameter("flip_x", 0.0)
        self.add_float_cpu_adaptable_parameter("flip_y", 0.0)
        super().initUniformsBinding(binding, program_name="")
        super().addProtectedUniforms([])

    def _parameter(self, name, fallback):
        parameters = self.getCpuAdaptableParameters()["program"]
        try:
            return float(parameters[name]["eval_function"]["value"])
        except (KeyError, TypeError, ValueError):
            return fallback

    def updateParams(self, af=None):
        """Pull the newest frame from the engine, if there is one."""
        if self.engine is None:
            return

        frame = self.engine.get_frame(since=self._last_frame_id)
        if frame is None:
            return

        # A reconnect can come back on a different profile.
        if self.depth_texture.size != (frame.width, frame.height):
            self.depth_texture.release()
            self.depth_texture = self.ctx.texture(
                (frame.width, frame.height), components=1, dtype="u2"
            )
            self.depth_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)

        self.depth_texture.write(frame.data)
        self._depth_scale = frame.depth_scale
        self._last_frame_id = frame.frame_id

    def bindUniform(self, af=None):
        super().bindUniform(af)

        near_mm = self._parameter("near_mm", DEFAULT_NEAR_MM)
        far_mm = self._parameter("far_mm", DEFAULT_FAR_MM)

        # Equal near and far would divide by zero in the shader.
        if far_mm == near_mm:
            far_mm = near_mm + 1.0

        self.program["near_mm"] = near_mm
        self.program["far_mm"] = far_mm
        self.program["depth_scale"] = self._depth_scale
        self.program["flip"] = (
            1.0 if self._parameter("flip_x", 0.0) else 0.0,
            1.0 if self._parameter("flip_y", 0.0) else 0.0,
        )

    def norender(self):
        return self.fbos[0].color_attachments[0]

    def render(self, af=None):
        self.updateParams(af)
        self.bindUniform(af)
        self.program["depth_map"] = 0
        self.depth_texture.use(0)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_DEPTH_INPUT)
class DepthInputNode(ShaderNode, Texture):
    op_title = "Depth Input"
    op_code = OP_CODE_DEPTH_INPUT
    content_label = ""
    content_label_objname = "depth_input"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])

        app = getattr(scene, "app", None)
        self.engine = getattr(app, "depth_engine", None)

        if self.engine is not None:
            self.engine.acquire()

        self.program = DepthInput(
            ctx=self.scene.ctx, win_size=(1920, 1080), engine=self.engine
        )
        self.eval()

    def remove(self):
        # Release before the node goes away, so the last node closing the graph
        # also closes the camera.
        if self.engine is not None:
            self.engine.release()
            self.engine = None

        super().remove()

    def render(self, audio_features=None):
        if self.engine is not None:
            self.grNode.setToolTip(self.engine.status_reason)

        if self.program is not None and self.program.already_called:
            return self.program.norender()

        return self.program.render(audio_features)
