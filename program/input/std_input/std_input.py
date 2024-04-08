import time
import numpy as np
from os.path import dirname, basename, isfile, join

from program.program_conf import SQUARE_VERT_PATH, get_square_vertex_data, register_program
from program.program_base import ProgramBase

from node.shader_node_base import ShaderNode, Input
from node.node_conf import register_node


DEBUG = True


OP_CODE_STDINPUT = 2

@register_program(OP_CODE_STDINPUT)
class StdInput(ProgramBase):

    def __init__(self, ctx=None, major_version=3, minor_version=3, win_size=(960, 540)):
        super().__init__(ctx, major_version, minor_version, win_size)

        self.title = "Std Input"

        self.initProgram()
        self.initParams()
        self.initFBOSpecifications()

    def initProgram(self, reload=False):
        vert_path = SQUARE_VERT_PATH
        frag_path = join(dirname(__file__), "std_input.glsl")
        self.loadProgramToCtx(vert_path, frag_path, reload)

    def initFBOSpecifications(self):
        self.required_fbos = 1
        fbos_specification = [
            [self.win_size, 4, 'f4'],
        ]
        for specification in fbos_specification:
            self.fbos_win_size.append(specification[0])
            self.fbos_components.append(specification[1])
            self.fbos_dtypes.append(specification[2])

    def initParams(self):
        pass

    def updateParams(self, af):
        pass

    def bindUniform(self, af):
        pass

    def render(self, textures, af=None):
        return textures[0]

    def norender(self):
        return self.fbos[0].color_attachments[0]

@register_node(OP_CODE_STDINPUT)
class StdInputNode(ShaderNode, Input):
    op_title = "Std Input"
    op_code = OP_CODE_STDINPUT
    content_label = ""
    content_label_objname = "std_input"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        self.program = StdInput(ctx=self.scene.ctx)
        self.eval()

    def restoreFBODependencies(self):
        self.scene.fbo_manager.restoreFBOUsability()
        for node in self.scene.nodes:
            node.markDirty()
            node.program.fbos = None
        self.eval()

    def evalInputNodes(self):
        if DEBUG: print("StdInputNode::evalInputNodes Eval Inputs:", self)
        # TODO Several Textures test
        input_nodes = self.getShaderInputs()
        if not input_nodes:
            self.grNode.setToolTip("Input is not connected")
            self.markInvalid()
            return None
        else:
            textures = []
            for input_node in input_nodes:
                texture = input_node.eval()
                textures.append(texture)
            if not len(textures):
                self.grNode.setToolTip("Input is not connected")
                self.markInvalid()
                return None
            return textures

    def evalImplementation(self):
        if DEBUG: print("StdInputNode::evalImplementation Eval Implementation:", self)
        # Find and Connect required fbos
        win_sizes, components, dtypes = self.program.getFBOSpecifications() 
        success = self.findAndConnectFbos(win_sizes, components, dtypes)
        print("FBOS INPUT OK")
        if not success:
            return False
        # Eval Input Node
        print("CONTAINER IS :", self.container)
        inputs_texture = self.evalInputNodes()
        print("INPUT TEXTURES OK", inputs_texture)
        if inputs_texture is None:
            return False
        for input_texture in inputs_texture:
            success = self.evalRendering(inputs_texture)
        # Eval Rendering
        if success:
            self.markInvalid(False)
            self.markDirty(False)
            self.grNode.setToolTip("")
            return True
        return False

    def getShaderInputs(self):
        if DEBUG: print("StdInputNode::getShaderInputs  current container is", self.container)
        if self.container is not None:
            ins = self.container.getShaderInputs()
            if DEBUG: print("StdInputNode::getShaderInputs  Inputs are", ins)
            return ins
        else:
            self.grNode.setToolTip("No Input connected")
            self.markDirty()

    def render(self, audio_features=None):
        input_nodes = self.getShaderInputs()
        if input_nodes is None:
            self.program.norender()
        texture = input_nodes[0].render(audio_features)
        input_texture = self.program.render([texture], audio_features)
        return input_texture
