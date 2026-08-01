from os.path import dirname, join

import moderngl
import numpy as np
from PyQt5.QtCore import QTimer

from depth.depth_engine import NO_FRAME_ID
from node.node_conf import register_node
from node.shader_node_base import DepthTexture, ShaderNode
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, name_to_opcode, register_program

OP_CODE_DEPTH_INPUT = name_to_opcode("DepthInput")

DEFAULT_NEAR_MM = 500.0
DEFAULT_FAR_MM = 4000.0

# Slow enough to be free, fast enough that a disconnect shows up while the user
# is still looking at the node.
TOOLTIP_REFRESH_MS = 500


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

        # Must precede initProgram: uniforms already protected when the shader
        # is parsed get no inspector entry at all. depth_map is the sampler unit
        # and depth_scale is reported by the sensor -- neither is meaningful to
        # drive from an expression. (Protecting them afterwards would not hide
        # them: ProgramBase.protectAdaptableParameters matches on the parameter
        # name, which is always the literal "eval_function", so it never marks
        # anything.)
        self.addProtectedUniforms(["depth_map", "depth_scale"])

        # initUniformsBinding needs the program loaded, since the binding keys
        # are the uniforms parsed out of the shader.
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initParams(self):
        # Bound to shader uniforms in initUniformsBinding, so these are the
        # values the inspector's expressions are evaluated against.
        self.near_mm = DEFAULT_NEAR_MM
        self.far_mm = DEFAULT_FAR_MM
        self.flip_x = 0.0
        self.flip_y = 0.0

        # Reported by the sensor, not a user control -- protected below.
        self.depth_scale = 1.0

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
        binding = {
            "iResolution": "win_size",
            "near_mm": "near_mm",
            "far_mm": "far_mm",
            "flip_x": "flip_x",
            "flip_y": "flip_y",
            "depth_scale": "depth_scale",
        }
        super().initUniformsBinding(binding, program_name="")

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

        # Measured at 1280x800@30 on an RTX 2080 SUPER: ~0.8ms median, so about
        # 2.5% of a 16.6ms frame at the camera's 31 uploads/s. Cheap enough that
        # no staging buffer or upload throttling is warranted.
        self.depth_texture.write(frame.data)

        self.depth_scale = frame.depth_scale
        self._last_frame_id = frame.frame_id

    def bindUniform(self, af=None):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

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
class DepthInputNode(ShaderNode, DepthTexture):
    op_title = "Depth Input"
    op_code = OP_CODE_DEPTH_INPUT
    content_label = ""
    content_label_objname = "depth_input"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])

        app = getattr(scene, "app", None)
        self.engine = getattr(app, "depth_engine", None)

        # Construct before acquiring: if GLSL compilation or FBO allocation
        # raises here, __init__ never completes and remove() never runs, so
        # an acquire() taken beforehand would never be matched by a
        # release() -- the camera would stay open for the process lifetime.
        self.program = DepthInput(
            ctx=self.scene.ctx, win_size=(1920, 1080), engine=self.engine
        )

        if self.engine is not None:
            self.engine.acquire()

        self.eval()

        # After eval(): evalImplementation clears the tooltip on success, so
        # starting the timer earlier would just have its first tick wiped.
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self.refreshStatusTooltip)
        self._status_timer.start(TOOLTIP_REFRESH_MS)

    def reload_program(self):
        # ShaderNode.reload_program rebuilds self.program via
        # self.program.__class__(ctx=..., win_size=...), which drops the
        # engine kwarg entirely -- DepthInput would come back with
        # engine=None and render a permanently transparent 1x1 texture with
        # no error. Override with the same shape as the base implementation,
        # re-injecting the engine this node already holds.
        state = self.serialize()

        program = self.program.__class__(
            ctx=self.scene.ctx, win_size=self.win_size, engine=self.engine
        )

        self._releaseDepthTexture()
        del self.program
        self.program = program

        self.deserialize(state, restore_window_size=False)
        self.markDirty()
        self.eval()

    def remove(self):
        # Stop first: a tick after grNode is torn down would touch a deleted
        # C++ object.
        self._status_timer.stop()

        # Release before the node goes away, so the last node closing the graph
        # also closes the camera.
        if self.engine is not None:
            self.engine.release()
            self.engine = None

        self._releaseDepthTexture()

        super().remove()

    def _releaseDepthTexture(self):
        # moderngl's context here is created without gc_mode, so
        # Texture.__del__ never releases GL memory on its own -- without an
        # explicit release() every reload_program (Resolution menu, or any
        # deserialize with restore_window_size=True) strands the old
        # program's depth_texture (up to 1280x800x2 bytes once streaming).
        # Guarded because construction may have failed part-way (no
        # self.program / no depth_texture yet), and because release() on an
        # already-released texture must not raise out of teardown.
        program = getattr(self, "program", None)
        texture = getattr(program, "depth_texture", None)
        if texture is None:
            return
        try:
            texture.release()
        except Exception:
            pass

    def refreshStatusTooltip(self):
        """Show the engine's status on the node.

        Driven by a timer rather than only from render(), because render() is
        reached only through a Screen node's input chain: an unconnected node
        would never report "no camera", which is exactly the case the status
        exists for. The timer also covers status changing while nothing in the
        graph re-evaluates -- a camera unplugged mid-session, or a reconnect
        succeeding.

        Compares against Qt's own state rather than a private cache:
        ShaderNode.evalImplementation unconditionally clears the tooltip to ""
        on every successful eval (construction, onInputChanged, markDirty,
        reload_program), which would silently defeat a "last written" cache --
        the cache would never see that change and would skip restoring it.
        """
        if self.engine is None or self.grNode is None:
            return

        tooltip = self.engine.status_reason
        if self.grNode.toolTip() != tooltip:
            self.grNode.setToolTip(tooltip)

    def render(self, audio_features=None):
        self.refreshStatusTooltip()

        if self.program is not None and self.program.already_called:
            return self.program.norender()

        return self.program.render(audio_features)
