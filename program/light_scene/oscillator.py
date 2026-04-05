import math
from node.node_conf import register_node
from node.shader_node_base import ShaderNode, LightScene
from program.program_conf import  name_to_opcode, register_program
from program.program_base import ProgramBase
from nodeeditor.node_graphics_socket import SocketType

OP_CODE_OSCILLATOR = name_to_opcode("oscillator")

@register_program(OP_CODE_OSCILLATOR)
class FlatPar(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "FlatPar"
        self.required_fbos = 0
        self.initParams()

    def initParams(self):
        self.phase = 0.
        self.time = 0.
        self.res = 0.

    def updateParams(self, af=None):
        self.res = math.sin(self.time + self.phase)
        self.time += 1.0 / 60.0

    def render(self, af=None):
        self.updateParams(af)

    def norender(self):
        return self.fbos[0].color_attachments[0]

@register_node(OP_CODE_OSCILLATOR)
class OscillatorNode(ShaderNode, LightScene):
    op_title = "Oscillator"
    op_code = OP_CODE_OSCILLATOR
    content_label = ""
    content_label_objname = "shader_oscillator"

    def __init__(self, scene):
        super().__init__(scene, inputs=[ ], outputs=[(1, None, SocketType.SCALAR)])
        self.light_engine = scene.app.light_engine
        self.program = FlatPar(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        self.render(audio_features)
