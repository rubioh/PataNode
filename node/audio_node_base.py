from PyQt5.QtGui import QImage
from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QLabel, QMessageBox

from nodeeditor.node_node import Node
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode
from nodeeditor.node_socket import LEFT_CENTER, RIGHT_CENTER
from nodeeditor.utils import dumpException


DEBUG = False


class AudioGraphicsNode(QDMGraphicsNode):
    def initSizes(self):
        super().initSizes()
        self.width = 160
        self.height = 50
        self.edge_roundness = 3
        self.edge_padding = 0
        self.title_horizontal_padding = 8
        self.title_vertical_padding = 10

    def initAssets(self):
        super().initAssets()
        self.icons = QImage("node/icons/status_icons.png")

    def paint(self, painter, QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, QStyleOptionGraphicsItem, widget)

        offset = 24.0

        if self.node.isDirty():
            offset = 0.0

        if self.node.isInvalid():
            offset = 48.0

        painter.drawImage(QRectF(-10, -10, 24.0, 24.0), self.icons, QRectF(offset, 0, 24.0, 24.0))

    def openDialog(self, msg):
        if isinstance(msg, list):
            msgs = ""

            for m in msg:
                msgs += m
        else:
            msgs = msg

        dialog = QMessageBox()
        dialog.setText(msgs)
        dialog.exec()


class AudioContent(QDMNodeContentWidget):
    def initUI(self):
        lbl = QLabel(self.node.content_label, self)
        lbl.setObjectName(self.node.content_label_objname)


class AudioNode(Node):
    icon = ""
    op_code = 0
    op_title = "Undefined"
    content_label = ""
    content_label_objname = "audio_node_bg"

    GraphicsNode_class = AudioGraphicsNode
    NodeContent_class = AudioContent

    def __init__(self, scene, inputs=[2, 2], outputs=[1]):
        super().__init__(scene, self.__class__.op_title, inputs, outputs)

        self.value = None  # Using to store output texture reference
        self.program = None

        # Current OpenGL ctx
        self.ctx = scene.ctx

        # It's really important to mark all nodes Dirty by default
        self.markDirty()

    def initSettings(self):
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER

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

    def evalImplementation(self):
        self.markInvalid(False)
        self.markDirty(False)
        self.grNode.setToolTip("")
        return True

    def eval(self):
        if not self.isDirty() and not self.isInvalid():
            if DEBUG:
                print(" _> returning cached %s value:" % self.__class__.__name__, self.value)

            return self.value

        try:
            _ = self.evalImplementation()
            return self.value
        except Exception as e:
            self.markInvalid()
            self.grNode.setToolTip(str(e))
            dumpException(e)

    def onInputChanged(self, socket=None):
        if DEBUG:
            print("%s::__onInputChanged" % self.__class__.__name__)

        self.markDirty()
        self.eval()

    def serialize(self):
        res = super().serialize()
        res["op_code"] = self.__class__.op_code
        return res

    def deserialize(self, data, hashmap={}, restore_id=True):
        res = super().deserialize(data, hashmap, restore_id)
        print("Deserialized ShaderNode '%s'" % self.__class__.__name__, "res:", res)
        return res
