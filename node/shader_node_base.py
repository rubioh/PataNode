from os.path import dirname, basename, isfile, join
import copy
import os
import inspect
import traceback

from PyQt5.QtGui import QImage
from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QLabel, QMessageBox

from nodeeditor.node_node import Node
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode
from nodeeditor.node_socket import LEFT_CENTER, RIGHT_CENTER
from nodeeditor.utils import dumpException

from program.program_conf import GLSLImplementationError, UnuseUniformError



DEBUG = False

class ShaderGraphicsNode(QDMGraphicsNode):
    def initSizes(self):
        super().initSizes()
        self.width = 160
        self.height = 74
        self.edge_roundness = 6
        self.edge_padding = 0
        self.title_horizontal_padding = 8
        self.title_vertical_padding = 10

    def initAssets(self):
        super().initAssets()
        self.icons = QImage("node/icons/status_icons.png")

    def paint(self, painter, QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, QStyleOptionGraphicsItem, widget)

        offset = 24.0
        if self.node.isDirty(): offset = 0.0
        if self.node.isInvalid(): offset = 48.0

        painter.drawImage(
            QRectF(-10, -10, 24.0, 24.0),
            self.icons,
            QRectF(offset, 0, 24.0, 24.0)
        )

    def openDialog(self, msg): 
        if isinstance(msg, list):
            msgs = ''
            for m in msg:
                msgs += m
        else:
            msgs = msg
        dialog = QMessageBox()
        dialog.setText(msgs)
        dialog.exec()


class ShaderContent(QDMNodeContentWidget):
    def initUI(self):
        lbl = QLabel(self.node.content_label, self)
        lbl.setObjectName(self.node.content_label_objname)


class ShaderNode(Node):
    icon = ""
    op_code = 0
    op_title = "Undefined"
    content_label = ""
    content_label_objname = "shader_node_bg"

    GraphicsNode_class = ShaderGraphicsNode
    NodeContent_class = ShaderContent

    def __init__(self, scene, inputs=[2,2], outputs=[1]):
        #inputs = [0] + inputs
        super().__init__(scene, self.__class__.op_title, inputs, outputs)

        self.value = None # Using to store output texture reference
        self.program = None
        # Current OpenGL ctx
        self.ctx = scene.ctx
        # it's really important to mark all nodes Dirty by default
        self.markDirty()


    def getAdaptableParameters(self):
        if self.program is not None:
            return self.program.getAdaptableParameters()
        return None
    
    def getUniformsBinding(self):
        if self.program is not None:
            return self.program.getUniformsBinding()
        return None

    def initSettings(self):
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER

    def restoreFBODependencies(self):
        pass

    def findAndConnectFbos(self, win_sizes, components=None, dtypes=None):
        if self.program.fbos is not None:
            # fbos already connected
            return True
        fbos = self.scene.fbo_manager.getFBO(
                win_sizes, components, dtypes
        )
        try:
            self.program.connectFbos(fbos)
        except AssertionError:
            print("Created fbos doesn't match the number of required fbos for %s"%self.program.__class__.__name__)
            self.grNode.setToolTip("No fbo's found")
            self.markInvalid()
            return False
        return True

    def evalInputNodes(self):
        print("Eval Inputs:", self)
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
            if len(textures) != len(self.inputs):
                self.grNode.setToolTip("Input is not connected")
                self.markInvalid()
                return None
            return textures

    def getShaderInputs(self):
        sockets = self.inputs
        ins = []
        for i, sockets in enumerate(sockets):
            if sockets.socket_type == 0: # socket_type 0 means audio_input
                continue
            ins += super().getInputs(i)
        return ins

    def evalRendering(self, textures=None):
        try:
            output_texture = self.program.render(textures)
            self.value = output_texture
            return True
        except Exception as e:
            self.grNode.setToolTip("Rendering error")
            self.markInvalid()
            self.grNode.openDialog(traceback.format_exception(e))
            print("Error during rendering")
            self.value = None
            return False
        return True

    def evalImplementation(self):
        print("Eval Implementation:", self)
        # Find and Connect required fbos
        win_sizes, components, dtypes = self.program.getFBOSpecifications() 
        success = self.findAndConnectFbos(win_sizes, components, dtypes)
        if not success:
            return False
        # Eval Input Node
        inputs = []
        for ins in self.inputs:
            if ins.socket_type == 0: # socket_type 0 means audio_input
                continue
            inputs.append(ins)
        if inputs:
            inputs_texture = self.evalInputNodes()
            if inputs_texture is None:
                return False
            for input_texture in inputs_texture:
                success = self.evalRendering(inputs_texture)
        else:
            success = self.evalRendering()
        # Eval Rendering
        if success:
            self.markInvalid(False)
            self.markDirty(False)
            self.grNode.setToolTip("")
            return True
        return False


    def eval(self):
        print("Eval:", self)
        if not self.isDirty() and not self.isInvalid():
            if DEBUG: print(" _> returning cached %s value:" % self.__class__.__name__, self.value)
            return self.value
        try:
            print('Eval Try', self)
            success = self.evalImplementation()
            return self.value
        except ValueError as e:
            self.markInvalid()
            self.grNode.setToolTip(str(e))
            self.markDescendantsDirty()
        except Exception as e:
            self.markInvalid()
            self.grNode.setToolTip(str(e))
            dumpException(e)

    def onInputChanged(self, socket=None):
        if DEBUG: print("%s::__onInputChanged" % self.__class__.__name__)
        self.markDirty()
        self.eval()

    def reloadGLSLCode(self):
        if DEBUG: print("Program before reloading is: ", self.program.program)
        try:
            self.program.reloadProgramSafely()
            self.markDirty()
            self.grNode.setToolTip("")
            self.eval()
        except GLSLImplementationError as e:
            self.markInvalid()
            self.grNode.setToolTip("Implementation Error")
            self.grNode.openDialog(traceback.format_exception(e))
            self.program.reloadPreviousProgramVersion()
        except UnuseUniformError as e:
            self.markInvalid()
            self.grNode.setToolTip("Unuse Uniform Error")
            self.grNode.openDialog(traceback.format_exception(e))
            self.program.reloadPreviousProgramVersion()
        if DEBUG: print("Program after reloading is: ", self.program.program)

    def getGLSLCodePath(self):
        return self.program.getGLSLCodePath()

    def openGLSLInTerminal(self, glsl_path):
        os.system('gnome-terminal --command="vim {}"'.format(glsl_path))
        print("Open in Vim the file %s"%glsl_path)

    def transform_audio_features(self, audio_features):
        pass


    def render(self, audio_features=None):
        pass

    def serialize(self):
        res = super().serialize()
        res['op_code'] = self.__class__.op_code

        adapt_params = copy.deepcopy(self.getAdaptableParameters())
        for program in adapt_params.keys():
            program_params = adapt_params[program]
            for uniform in program_params.keys():
                del program_params[uniform]['eval_function']['connect']
        res['adaptable_parameters'] = adapt_params
        uniforms_binding = self.program.getUniformsBinding()._all_bindings
        res['uniforms_binding'] = uniforms_binding
        return res

    def deserialize(self, data, hashmap={}, restore_id=True):
        res = super().deserialize(data, hashmap, restore_id)

        adapt_params = data['adaptable_parameters']
        node_params = self.getAdaptableParameters()
        for program in adapt_params.keys():
            program_params = adapt_params[program]
            for uniform in program_params.keys():
                eval_func = program_params[uniform]['eval_function']['value']
                node_params[program][uniform]['eval_function']['value'] = eval_func
        uniforms_binding = data['uniforms_binding']
        self.program.restoreUniformsBinding(uniforms_binding)
        print("Deserialized ShaderNode '%s'" % self.__class__.__name__, "res:", res)
        return res





class Utils(): node_type_reference = "Utils"
class Scene(): node_type_reference = "Scenes"
class Output(): node_type_reference = "Outputs"
class Texture(): node_type_reference = "Textures"
class Effects(): node_type_reference = "Effects"
class Colors(): node_type_reference = "Colors"
