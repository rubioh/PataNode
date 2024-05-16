import time
import numpy as np
from PIL import Image
from os.path import dirname, basename, isfile, join
import moderngl
from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program, name_to_opcode
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Scene
from node.node_conf import register_node

OP_CODE_NEONPARTY = name_to_opcode('NeonParty')

@register_program(OP_CODE_NEONPARTY)
class NeonParty(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Neon Party"
        self.win_size = win_size
        self.hwin_size = (int(self.win_size[0] / 2), int(self.win_size[1] / 2))
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initParams(self):
        self.iResolution = self.hwin_size
        self.current_texture = 0
        self.was_on_chill = False
        self.shape = 0
        self.animate = 0
        self.iTime = 0.
        self.textures = [None, None]
        self.frame = 0
        self.low1 = 0
        self.ro = 0
        self.on_chill = 0
        self.low2 = 0
        self.drop = False
        self.drop_t = 0
        jpg_image = Image.open("./assets/lichen.jpg")
        bmp_image = jpg_image.convert("RGB")
        b = list(bmp_image.getdata())
        b2 = []
        for x in b:
            for data in x:
                b2.append(data)
        b = bytes(b2)
        self.lichen_texture = self.ctx.texture(
            (1024, 1024), components=3, dtype="f1", data=b
        )
        self.lichen_texture.repeat_x = True
        self.lichen_texture.repeat_y = True
        self.beat_count = 0

    def initFBOSpecifications(self):
        self.required_fbos = 2
        fbos_specification = [
            [self.hwin_size, 4, 'f4'],
            [self.win_size, 4, 'f4']
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name='')

    def initUniformsBinding(self):
        binding = {
                'iTime': 'iTime',
                'iResolution': 'iResolution',
                'stride':'stride',
                'beat_count':'beat_count',
                'low1':'low1',
                'low2':'low2',
                'drop':'drop',
                'animate':'animate',
                'shape':'shape',
                'on_chill':'on_chill',
                'ro':'ro'
                }
        super().initUniformsBinding(binding, program_name='')
        super().addProtectedUniforms(
                []
        )

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "NeonParty.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "reconstruct.glsl")
        self.loadProgramToCtx(vert_path, frag_path, False, name='reconstruct_')

    def render(self, af=None, stride = 0):
        self.fbos[0].color_attachments[0].filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.stride = stride
        self.lichen_texture.use(0)
        self.updateParams(af)
        self.bindUniform(af)
        self.fbos[0].use()
        self.vao.render()
        self.textures[self.frame] = self.fbos[0].color_attachments[0]
        self.reconstruct_program["iChannel0"] = 0
        self.reconstruct_program["iChannel1"] = 0
        self.reconstruct_program["iResolution"] = self.win_size
        if self.textures[0]:
            self.textures[0].use(0)
        if self.textures[1]:
            self.textures[1].use(1)
        self.fbos[1].use()
        self.reconstruct_vao.render()
        return self.fbos[1].color_attachments[0]

    def updateParams(self, af):
        if not af:
            return
        self.frame = (self.frame + 1) % 2
        if af["on_kick"]:
            self.beat_count = self.beat_count + 1
        if af["on_chill"] and not self.drop:
            self.was_on_chill = True
        if self.was_on_chill and af["on_chill"] < 0.9 and not self.drop:
            self.drop = True
            self.drop_t = time.perf_counter()
            self.waf_on_chill = False
        if (
            self.drop and time.perf_counter() - self.drop_t > 15
        ):  # or af["on_chill"] > .9:
            self.drop = False
            self.was_on_chill = False
        self.animate = False
        if self.beat_count % 100 < 25 or self.drop:
            if af["on_kick"]:
                self.shape = not self.shape
        elif self.beat_count % 100 < 50:
            self.animate = True
        else:
            self.shape = 1
        self.iTime = af["time"] * 1.0
        self.stride = float(self.frame)
        self.beat_count = float(self.beat_count)
        self.low1 = af["low"][1]
        self.low2 = af["low"][0]
        self.drop = float(self.drop)
        self.shape = float(self.shape)
        self.animate = float(self.animate)
        self.on_chill = af["on_chill"]
        self.ro = af["high"][1]

    def norender(self):
        return self.fbos[0].color_attachments[0]

@register_node(OP_CODE_NEONPARTY)
class NeonPartyNode(ShaderNode, Scene):
    op_title = "Neon Party"
    op_code = OP_CODE_NEONPARTY
    content_label = ""
    content_label_objname = "shader_neonparty"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[1])
        self.program = NeonParty(ctx=self.scene.ctx, win_size=(1920,1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program.already_called:
            return self.program.norender()
        else:
            output_texture = self.program.render(audio_features)
        self.lastrender = output_texture
        return output_texture
