import time

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QLabel, QMessageBox

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode
from nodeeditor.node_node import Node
from nodeeditor.node_socket import LEFT_CENTER, RIGHT_CENTER
from nodeeditor.utils import dumpException
from program.program_conf import (
    GLSLImplementationError,
    UnuseUniformError,
    name_to_opcode,
)


class LightGraphicsNode(QDMGraphicsNode):
    def initSizes(self):
        super().initSizes()
        self.width = 160
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

        if self.node.isDirty():
            offset = 0.0

        if self.node.isInvalid():
            offset = 48.0

        painter.drawImage(
            QRectF(-10, -10, 24.0, 24.0), self.icons, QRectF(offset, 0, 24.0, 24.0)
        )

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


class LightContent(QDMNodeContentWidget):
    def initUI(self):
        lbl = QLabel(self.node.content_label, self)
        lbl.setObjectName(self.node.content_label_objname)


class LightNode(Node):
    icon = ""
    op_code = 0
    op_title = "Undefined"
    content_label = ""
    content_label_objname = "shader_node_bg"

    GraphicsNode_class = LightGraphicsNode
    NodeContent_class = LightContent

    def __init__(self, scene, inputs=[2, 2], outputs=[1]):
        #       inputs = [0] + inputs
        super().__init__(scene, self.__class__.op_title, inputs, outputs)
        self.should_update_preview = True
        self.value = None  # Using to store output texture reference
        self.program = None
        self._container = None  # GraphContainer reference

        # Current OpenGL ctx
        self.ctx = scene.ctx

        # It's really important to mark all nodes Dirty by default
        self.markDirty()

        # Evaluation Logics for loop in Graph
        self._evaluate = False
        self._in_evaluation = False
        self.previous_evaluation_time = time.time()

    @property
    def container(self):
        return self._container

    @container.setter
    def container(self, value):
        self._container = value

    @property
    def already_called(self):
        return self.program.already_called

    @already_called.setter
    def already_called(self, value: bool):
        if self.program is not None:
            self.program.already_called = value

    @property
    def in_evaluation(self):
        return self._in_evaluation

    @in_evaluation.setter
    def in_evaluation(self, value: bool):
        self._in_evaluation = value

    @property
    def evaluate(self):
        return self._evaluate

    @evaluate.setter
    def evaluate(self, value: bool):
        self._evaluate = value

    def initSettings(self):
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER


class LightOutput:
    node_type_reference = "Light Output"