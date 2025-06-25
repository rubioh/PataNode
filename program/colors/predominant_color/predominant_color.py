import numpy as np

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Colors
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, register_program, name_to_opcode


OP_CODE_PREDOMINANTCOLOR = name_to_opcode("predominantcolor")


@register_program(OP_CODE_PREDOMINANTCOLOR)
class PredominantColor(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(480, 270)):
        win_size = (480, 270)  # PROTEGE ON PEUT PAS MODIFIER
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "Predominant Color"

        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

    def initFBOSpecifications(self):
        self.required_fbos = self.N_pass
        Ks = [2 ** (i + 1) for i in range(self.N_pass)]
        fbos_specification = [
            [(self.win_size[0] // K, self.win_size[1] // K), 4, "f4"] for K in Ks
        ]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Histogram/hist.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="hist_")

    def initParams(self):
        self.N_pass = 7

        if self.win_size == (480, 270):
            self.N_pass = 7

        self.iChannel0 = 1
        self.buf_col = np.zeros(3)
        self.hist = np.zeros((3, 6, 4))

    def getBufferColor(self, col_tex, j):
        col_tex = col_tex.reshape(-1, 4)
        self.hist[j] = self.hist[j] * 0.7 + 0.3 * col_tex
        max_a = 0
        idx = 0

        for i in range(self.hist.shape[0]):
            if self.hist[j][i, -1] > max_a:
                max_a = self.hist[j][i, -1]
                idx = i

        col = self.hist[j][idx, :3] * 0.3 + self.buf_col[j] * 0.7
        out_col = self.hist[j][idx, :3]
        self.buf_col = out_col
        return col, out_col

    def initUniformsBinding(self):
        binding = {}
        super().initUniformsBinding(binding, program_name="hist_")
        self.addProtectedUniforms(["iChannel0"])

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="hist_")

    def render(self, texture, af=None):
        self.bindUniform(af)

        if texture is None:
            return

        self.hist_program["iChannel0"] = self.iChannel0
        texture.use(1)
        colors_to_skip = [[0] * 3, [0] * 3, [0] * 3]
        self.buf_col = np.zeros((3, 3))

        for j in range(1):
            self.hist_program["to_skip_size"] = j
            self.hist_program["to_skip"] = colors_to_skip
            self.hist_program["pass_number"] = 0
            self.fbos[0].use()
            self.hist_vao.render()

            for i in range(0, self.N_pass - 1):
                #               self.fbo_hist[1 + i].clear()
                self.hist_program["pass_number"] = i + 1
                self.fbos[i].color_attachments[0].use(1)
                self.fbos[i + 1].use()
                self.hist_vao.render()

            raw_bytes = self.fbos[-1].color_attachments[0].read()
            buf = np.frombuffer(raw_bytes, dtype="f4")
            col, out_col = self.getBufferColor(buf, j)
            colors_to_skip[j] = out_col
        return self.buf_col

    def norender(self):
        return self.buf_col


@register_node(OP_CODE_PREDOMINANTCOLOR)
class PredominantColorNode(ShaderNode, Colors):
    op_title = "Predominant Color"
    op_code = OP_CODE_PREDOMINANTCOLOR
    content_label = ""
    content_label_objname = "shader_predominant_color"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[])
        self.program = PredominantColor(ctx=self.scene.ctx, win_size=(480, 270))
        self.eval()

    def render(self, texture=None):
        if self.program is not None and self.program.already_called:
            return self.program.norender()

        if texture is None:
            return self.program.norender()

        buffer_col = self.program.render(texture)
        return buffer_col
