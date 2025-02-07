import random
import time

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Utils
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_RANDOM = name_to_opcode("random")


@register_program(OP_CODE_RANDOM)
class Random(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "random"

        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

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
        frag_path = join(dirname(__file__), "random.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initParams(self):
        self.index = 0
        self.on_kick = False
        self.kick_index = 0
        self.iChannel0 = 1
        self.last_idx = 0
        self.range_start = 5
        self.range_end = 10
        self.is_transi = False
        self.time_for_next = 0

    def initUniformsBinding(self):
        binding = {"iChannel0": "iChannel0", "iResolution": "win_size"}
        self.add_text_edit_cpu_adaptable_parameter("range_start", self.range_start, lambda: 0)
        self.add_text_edit_cpu_adaptable_parameter("range_end", self.range_end, lambda: 0)
        super().initUniformsBinding(binding, program_name="")
        self.addProtectedUniforms(["iChannel0"])

    def updateParams(self, l, af):
        self.range_start = float(self.getCpuAdaptableParameters()["program"]["range_start"]["eval_function"]["value"])
        self.range_end = float(self.getCpuAdaptableParameters()["program"]["range_end"]["eval_function"]["value"])
        if af is None or l is None:
            return
        if af["on_kick"] and not self.on_kick and self.is_transi:
            self.on_kick = True
            self.kick_index = self.kick_index + 1
            if self.kick_index > 10:
                self.is_transi == False
                self.kick_index = 0
                self.on_kick = False
        else:
            self.on_kick = False

        if time.perf_counter() > self.time_for_next:
            self.is_transi = True
            self.last_idx = self.index
            self.index = random.randrange(0, l)
            if self.range_start >= self.range_end:
                self.time_for_next = time.perf_counter() + random.randrange(self.range_end, self.range_start + 1)
            else:
                self.time_for_next = time.perf_counter() + random.randrange(self.range_start, self.range_end)

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, texture, l=None, af=None):
        self.bindUniform(af)
        self.updateParams(l, af)
        texture[0].use(1)
        self.fbos[0].use()
        self.vao.render()
        return self.fbos[0].color_attachments[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]

@register_node(OP_CODE_RANDOM)
class RandomNode(ShaderNode, Utils):
    op_title = "Random"
    op_code = OP_CODE_RANDOM
    content_label = ""
    content_label_objname = "shader_random"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1, 1, 1, 1, 1], outputs=[3])
        self.program = Random(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        l = len(input_nodes)
        if not l or self.program.already_called:
            return self.program.norender()

        if input_nodes[self.program.index]:
            indexes = [self.program.index, self.program.last_idx]
            index = self.program.index
            if self.program.is_transi:
                index = indexes[self.program.kick_index % 2]
            texture = input_nodes[index].render(audio_features)
        output_texture = self.program.render([texture], l, audio_features)
        return output_texture
