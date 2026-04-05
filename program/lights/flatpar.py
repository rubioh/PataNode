


from node.node_conf import register_node
from node.shader_node_base import Light
from node.light_node_base import LightNode
from program.program_conf import  name_to_opcode, register_program
from program.program_base import ProgramBase
from nodeeditor.node_graphics_socket import SocketType

OP_CODE_FLATPAR = name_to_opcode("flatpar")

@register_program(OP_CODE_FLATPAR)
class FlatPar(ProgramBase): # remove programbase
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "FlatPar"
        self.required_fbos = 0
        self.name = ""
        self.initParams()
        self.initUniformsBinding()

    def initParams(self):
        self.dmx_offset = 0.

    def initUniformsBinding(self):
#        self.add_text_edit_cpu_adaptable_parameter(
#            "dmx_offset", self.dmx_offset, lambda: 0
#        )
        super().initUniformsBinding({}, program_name="")

    def updateParams(self, af=None):
        pass

    def render(self, af=None):
        self.updateParams(af)

    def norender(self):
        return self.fbos[0].color_attachments[0]

@register_node(OP_CODE_FLATPAR)
class FlatparNode(LightNode, Light):
    op_title = "Flatpar"
    op_code = OP_CODE_FLATPAR
    content_label = ""
    content_label_objname = "shader_flatpar"

    def __init__(self, scene):
        super().__init__(scene, inputs=[(1, "Red", SocketType.SCALAR),
                                        (1, "Green", SocketType.SCALAR),
                                        (1, "Blue", SocketType.SCALAR),
                                        (1, "White", SocketType.SCALAR),
                                        (1, "Amber", SocketType.SCALAR),
                                        (1, "UV", SocketType.SCALAR),
                                        (1, "Dimmer", SocketType.SCALAR),
                                        (1, "Strobe", SocketType.SCALAR), ], outputs=[])
        self.light_engine = scene.app.light_engine
       # self.program = FlatPar(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        self.render(audio_features)
