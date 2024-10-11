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

from node.shader_node_base import ShaderNode, LED
from node.node_conf import register_node

OP_CODE_LED_SYMETRY = name_to_opcode("led_symetry")


@register_program(OP_CODE_LED_SYMETRY)
class LedSymetry(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "LedSymetry"

        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()
        self.initParams()

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, "f4"],
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "led_symetry.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initUniformsBinding(self):
        binding = {
            "iChannel0": "iChannel0",
            "mode": "led_symetry_mode",
            "kick_count": "kick_count",
            "mode_mask": "mode_mask",
            "blink_force": "blink_force",
            "no_sym_mode": "no_sym_mode",
            "on_tempo": "on_tempo",
            "real_kick_count": "real_kick_count",
            "black_mode": "black_mode",
            "black": "black",
            "go_strobe": "go_strobe",
            "noise_time": "noise_time",
            "mode_2_sym": "mode_2_sym",
        }
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def initParams(self):
        self.iChannel0 = 1
        self.chill = False
        self.led_symetry_mode = 1
        self.kick_count = 0
        self.mode_mask = 1
        self.time_mask = 0
        self.wait_mode = 0

        self.blink = 0
        self.blink_force = 0

        self.no_sym_mode = 0
        self.on_tempo = 0
        self.real_kick_count = 0
        self.float_no_sym_mode = 0

        self.black = 0
        self.black_mode = 0
        self.noise_time = 0

        self.in_mini_chill = 0
        self.time_strobe = 0
        self.go_strobe = 0

        self.mode_2_sym = 0

    def updateParams(self, af=None):
        if af is None:
            return
        self.kick_count = af["kick_count"] % 4

        self.time_mask += .0007*.33
        self.mode_mask = int(self.time_mask%2)
        
        if af["mini_chill"] and self.wait_mode>10:
            self.led_symetry_mode += 1 
            self.float_no_sym_mode += 1
            self.wait_mode = 0
        self.led_symetry_mode %= 6
        self.wait_mode += 1/60
    
        self.blink += .0009*.31
        self.blink %= 2
        blink = int(self.blink) + af["smooth_low"]
        self.blink_force = np.clip(blink, 0, 1)

        self.float_no_sym_mode += 0.00074*.36
        self.no_sym_mode = int(self.float_no_sym_mode%5)
        self.real_kick_count = af["kick_count"]
        self.on_tempo = af["on_tempo2"]

        if af["mini_chill"]:
            self.black = 1
            self.in_mini_chill = 1
        else:
            self.black = 0
            self.black_mode += 1
            if self.in_mini_chill:
                if np.random.randint(10)>7:
                    self.go_strobe = 1
                    self.time_strobe = 1
                self.in_mini_chill = 0
        self.time_strobe -= 1/60*.25
        self.time_strobe = max(self.time_strobe, 0)
        if self.time_strobe == 0:
            self.go_strobe = 0
        self.black_mode %= 2
        self.noise_time += .001

        self.mode_2_sym += .000013
        self.mode_2_sym %= 4


    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.bindUniform(af)
        self.updateParams(af)
        textures[0].use(1)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]


@register_node(OP_CODE_LED_SYMETRY)
class LedSymetryNode(ShaderNode, LED):
    op_title = "LedSymetry"
    op_code = OP_CODE_LED_SYMETRY
    content_label = ""
    content_label_objname = "shader_led_symetry"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        self.program = LedSymetry(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if not len(input_nodes) or self.program.already_called:
            return self.program.norender()
        texture = input_nodes[0].render(audio_features)
        output_texture = self.program.render([texture], audio_features)
        return output_texture
