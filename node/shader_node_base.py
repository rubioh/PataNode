from PyQt5.QtGui import QImage
from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QLabel

from nodeeditor.node_node import Node
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode
from nodeeditor.node_socket import LEFT_CENTER, RIGHT_CENTER
from nodeeditor.utils import dumpException

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
        super().__init__(scene, self.__class__.op_title, inputs, outputs)

        self.value = None # Using to store output texture reference
        self.program = None
        # Current OpenGL ctx
        self.ctx = scene.ctx

        # it's really important to mark all nodes Dirty by default
        self.markDirty()

    def restoreFBODependencies(self):
        pass

    def initSettings(self):
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER

    def findAndConnectFbos(self, win_sizes, components=None, dtypes=None):
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
        # TODO Several Textures test
        input_node = self.getInput(0)
        if not input_node:
            self.grNode.setToolTip("Input is not connected")
            self.markInvalid()
            return None
        else:
            input_node.eval()
            return input_node.value

    def evalRendering(self, textures=None):
        try:
            output_texture = self.program.render(textures)
            self.value = output_texture
            return True
        except:
            self.grNode.setToolTip("Rendering error")
            self.markInvalid()
            print("Error during rendering")
            self.value = None
            return False
        return True

    def evalImplementation(self):
        # Find and Connect required fbos
        win_sizes, components, dtypes = self.program.getFBOSpecifications() 
        success = self.findAndConnectFbos(win_sizes, components, dtypes)
        if not success:
            return False
        # Eval Input Node
        if self.inputs:
            inputs_texture = self.evalInputNodes()
            if inputs_texture is None:
                return False
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
        if not self.isDirty() and not self.isInvalid():
            if DEBUG: print(" _> returning cached %s value:" % self.__class__.__name__, self.value)
            return self.value
        try:
            val = self.evalImplementation()
            return val
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


    def serialize(self):
        res = super().serialize()
        res['op_code'] = self.__class__.op_code
        return res

    def deserialize(self, data, hashmap={}, restore_id=True):
        res = super().deserialize(data, hashmap, restore_id)
        print("Deserialized ShaderNode '%s'" % self.__class__.__name__, "res:", res)
        return res

    def render(self):
        pass
