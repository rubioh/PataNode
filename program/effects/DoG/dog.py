import cv2
import numpy as np

from os.path import dirname, join

from node.node_conf import register_node
from node.shader_node_base import ShaderNode, Effects
from program.program_base import ProgramBase
from program.program_conf import SQUARE_VERT_PATH, name_to_opcode


OP_CODE_DOG = name_to_opcode("DoGDoG")


class DoG(ProgramBase):
    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        """
        Difference of Gaussians (DoG)
        band pass filters
        required a textures and its SST to performs the DoG
        """
        super().__init__(ctx, major_version, minor_version, win_size)
        self.title = "DoG"

        self.initParams()
        self.initProgram()
        self.initFBOSpecifications()
        self.initUniformsBinding()

    def initTexture(self):
        image = cv2.imread("data/test3.png", cv2.IMREAD_UNCHANGED)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = np.flip(image, 0).copy(order="C")
        self.texture = self.ctx.texture(image.shape[:2][::-1], image.shape[2], image)

        hatch = cv2.imread("data/hatch_gb.png", cv2.IMREAD_UNCHANGED)
        hatch = cv2.cvtColor(hatch, cv2.COLOR_BGR2RGB)
        hatch = np.flip(hatch, 0).copy(order="C")
        self.hatch = self.ctx.texture(hatch.shape[:2][::-1], hatch.shape[2], hatch)

    def initFBOSpecifications(self):
        rfbos = 3
        self.required_fbos = rfbos
        fbos_specification = [[self.win_size, 4, "f4"] for i in range(rfbos)]

        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Blur/vblur.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="vblur_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "Blur/hblur.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="hblur_")

        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "DoG.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload, name="")

    def initParams(self):
        self.initTexture()
        self.sigma = 1.0  # std LIC blur
        self.sigmaE = 2.0  # std orthogonal edge blur
        self.sigmaA = 3.0  # std LIC AA blur
        self.k = 4.5  # Mul factor between DoG (sigma and sigmaE)

        self.tau = 2000.0
        self.epsilon = 0.0
        self.phi = 0.01
        self.mode = 3

        self.sketchy = {
            "sigma": 0.5,
            "k": 1.7795275590555118,
            "sigmaE": 1.0,
            "sigmaA": 7.681102362204724,
            "tau": 39.370078,
            "phi": 0.29133,
            "epsilon": 3.14960629921,
            "mode": 0,
        }
        self.faces = {
            "sigma": 0.5,
            "k": 1.7795275590555118,
            "sigmaE": 1.0,
            "sigmaA": 8.8771102362204724,
            "tau": 15.740078,
            "phi": 1.0,
            "epsilon": 6.69960629921,
            "mode": 1,
        }
        self.smoothy = {
            "sigma": 0.5708,
            "k": 1.63795275590555118,
            "sigmaE": 1.0,
            "sigmaA": 10.0,
            "tau": 291.740078,
            "phi": 1.0,
            "epsilon": 3.149960629921,
            "mode": 2,
        }
        self.flowy = {
            "sigma": 0.677,
            "k": 1.35433,
            "sigmaE": 1.9212,
            "sigmaA": 6.9330,
            "tau": 1000.740078,
            "phi": 0.023622,
            "epsilon": 0.0,
            "mode": 3,
        }
        self.hatchy = {
            "sigma": 0.5,
            "k": 1.93795275590555118,
            "sigmaE": 2.275,
            "sigmaA": 1.472,
            "tau": 102.740078,
            "phi": 10.0,
            "epsilon": 3.149960629921,
            "mode": 3,
        }
        self.kuwa = {
            "sigma": 0.5,
            "k": 2.343795,
            "sigmaE": 1.0,
            "sigmaA": 5.0,
            "tau": 39.37,
            "phi": 0.06299,
            "epsilon": 23.8976,
            "mode": 0,
        }
        self.preset = ["smoothy", "faces", "sketchy", "hatchy", "flowy", "kuwa"]
        self.change_params(params={"smoothy": 1.0})

        self.iChannel0 = 0
        self.BaseTex = 1
        self.Hatch = 2
        self.DoG = 3
        self.SST = 4

    def change_params(self, params=None):
        for m in params.keys():
            if m in self.preset:
                for k, v in getattr(self, m).items():
                    setattr(self, k, v)

    def initUniformsBinding(self):
        binding = {
            "iResolution": "win_size",
            "tau": "tau",
            "eps": "epsilon",
            "phi": "phi",
            "mode": "mode",
            "BaseTex": "BaseTex",  # 87
            "Hatch": "Hatch",  # 90
            "DoG": "DoG",  # 88
        }
        super().initUniformsBinding(binding, program_name="")
        binding = {
            "iResolution": "win_size",
            "sigmaE": "sigmaE",
            "iChannel0": "iChannel0",
            "k": "k",
            "SST": "SST",  # 86
        }
        super().initUniformsBinding(binding, program_name="vblur_")
        binding = {
            "iResolution": "win_size",
            "iChannel0": "iChannel0",
            "sigma": "sigma",
            "k": "k",
            "SST": "SST",  # 86
        }
        super().initUniformsBinding(binding, program_name="hblur_")
        self.addProtectedUniforms(["iChannel0", "SST", "BaseTex", "Hatch", "DoG"])

    def updateParams(self, af=None):
        pass

    def bindUniform(self, af):
        super().bindUniform(af)
        self.programs_uniforms.bindUniformToProgram(af, program_name="vblur_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="hblur_")
        self.programs_uniforms.bindUniformToProgram(af, program_name="")

    def render(self, textures, af=None):
        self.updateParams(af)
        self.bindUniform(af)

        texture = textures[0]
        SST = textures[1]

        texture.use(0)
        SST.use(4)
        self.fbos[0].use()
        self.vblur_vao.render()

        self.fbos[0].color_attachments[0].use(0)
        SST.use(4)
        self.fbos[1].use()
        self.hblur_vao.render()

        texture.use(1)
        self.hatch.use(2)
        self.fbos[1].color_attachments[0].use(3)
        SST.use(4)
        self.fbos[2].use()
        self.vao.render()
        return self.fbos[2].color_attachments[0]

    def norender(self):
        return self.fbos[2].color_attachments[0]


@register_node(OP_CODE_DOG)
class DoGNode(ShaderNode, Effects):
    op_title = "DoG"
    op_code = OP_CODE_DOG
    content_label = ""
    content_label_objname = "shader_dog"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1, 2], outputs=[3])
        self.program = DoG(ctx=self.scene.ctx, win_size=(1920, 1080))
        self.eval()

    def render(self, audio_features=None):
        if self.program is not None and self.program.already_called:
            return self.program.norender()

        input_nodes = self.getShaderInputs()

        if len(input_nodes) < 2:
            return self.program.norender()

        texture = input_nodes[0].render(audio_features)
        sst = input_nodes[1].render(audio_features)

        if texture is None or sst is None:
            return self.program.norender()

        output_texture = self.program.render([texture, sst], audio_features)
        return output_texture
