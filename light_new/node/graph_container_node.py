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

# from node.node_conf import register_node

DEBUG = False


class GraphContainerGraphicsNode(QDMGraphicsNode):
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


class GraphContainerNodeContent(QDMNodeContentWidget):
    def initUI(self):
        lbl = QLabel(self.node.content_label, self)
        lbl.setObjectName(self.node.content_label_objname)


# @register_node("GRAPHCONTAINER")
class GraphContainerNode(Node):
    icon = ""
    op_code = 666
    op_title = "GraphContainer"
    content_label = ""
    content_label_objname = "graph_container_node_bg"

    GraphicsNode_class = GraphContainerGraphicsNode
    NodeContent_class = GraphContainerNodeContent

    def __init__(self, scene, inputs=[], outputs=[3]):
        # inputs = [0] + inputs
        super().__init__(scene, self.__class__.op_title, inputs, outputs)
        self.app = None
        self.value = None  # Using to store output texture reference
        self.program = None
        self.graph = None
        self.subwnd = None
        # Current OpenGL ctx
        self.ctx = scene.ctx
        # it's really important to mark all nodes Dirty by default
        self.markDirty()

    def setApp(self, app):
        self.app = app

    def initSettings(self):
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER

    def openNewGraph(self):
        previous_wnd = self.subwnd
        self.graph, self.subwnd = self.app.onFileOpen(graph=True)
        self.title = "Graph Ctn : \n\n" + self.graph.title.split(".")[0]
        if previous_wnd is not None:
            self.app.mdiArea.removeSubWindow(previous_wnd)
        for node in self.scene.nodes:
            node.container = self
        self.graph.setGraphContainerNode(self)
        self.graph.bindToContainer()
        self.updateInputSocket()

    def updateInputSocket(self):
        input_sockets = [1 for i in range(len(self.graph.input_nodes))]
        output_sockets = [3 for i in range(len(self.outputs))]
        self.initSockets(input_sockets, output_sockets, reset=True)

    def restoreFBODependencies(self):
        for node in self.graph.output_nodes:
            node.restoreFBODependencies()
        self.eval()

    def eval(self):
        if self.graph is None:
            self.grNode.setToolTip("GCNode::eval No Graph Associated")
            self.markInvalid()
            if DEBUG:
                print("GCNode::eval No Graph Associated to this graph container node")
            return False
        output_nodes = self.graph.output_nodes
        if len(output_nodes) == 0:
            self.grNode.setToolTip("No Std Output found")
            self.markInvalid()
            if DEBUG:
                print("GCNode::eval No Std Output found to this graph container node")
            return False
        if DEBUG:
            print("Start evaluation nodes from the Graph")
        for node in self.graph.output_nodes:
            if DEBUG:
                print("GCNode::eval Evaluate the node : ", node)
            success = node.eval()
            if DEBUG:
                print("Evaluation of node", node, "is ", success)
            if not success:
                self.grNode.setToolTip("Graph evaluation failed")
                self.markInvalid()
                return False
        self.markDirty(False)
        self.markInvalid(False)
        self.grNode.setToolTip("")
        return success

    def getShaderInputs(self):
        sockets = self.inputs
        if DEBUG:
            print("GCNodes::getShaderInputs():  Container Sockets are", sockets)
        ins = []
        for i, sockets in enumerate(sockets):
            if sockets.socket_type == 0:  # socket_type 0 means audio_input
                continue
            ins += super().getInputs(i)
        if DEBUG:
            print("GCNodes::getShaderInputs():  Container Inputs are", ins)
        return ins

    def render(self, audio_features=None):
        textures = self.graph.render(audio_features)
        return textures[0]

    def serialize(self):
        res = super().serialize()
        return res

    def deserialize(self, data, hashmap={}, restore_id=True):
        res = super().deserialize(data, hashmap, restore_id)
        return res
