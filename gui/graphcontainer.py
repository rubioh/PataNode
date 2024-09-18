import os
import time

from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QMdiArea,
    QWidget,
    QDockWidget,
    QAction,
    QMessageBox,
    QFileDialog,
)
from PyQt5.QtCore import Qt, QSignalMapper

from nodeeditor.utils import loadStylesheets
from nodeeditor.node_editor_window import NodeEditorWindow
from nodeeditor.node_edge import Edge
from nodeeditor.utils import dumpException, pp

from gui.subwindow import PataNodeSubWindow
from gui.widgets.drag_listbox_widget import QDMDragListbox
from gui.widgets.shader_widget import ShaderWidget
from gui.widgets.inspector_widget import QDMInspector
from gui.widgets.audio_widget import AudioLogWidget

from program.output.screen.screen import ScreenNode
from program.output.std_output.std_output import StdOutputNode
from program.input.std_input.std_input import StdInputNode

from node.node_conf import SHADER_NODES, AUDIO_NODES


DEBUG = False


class GraphContainerSubWindow(PataNodeSubWindow):

    def __init__(self, app=None):
        super().__init__(app)
        self.graph_container_node = None
        self.output_nodes = []
        self.input_nodes = []

    def setGraphContainerNode(self, node):
        self.graph_container_node = node

    def bindToContainer(self):
        for node in self.scene.nodes:
            node.container = self.graph_container_node
            if DEBUG:
                print("GCSubWindow::bindToContainer Bind container to node", node)

    def searchOutputNodes(self):
        for node in self.scene.nodes:
            if isinstance(node, StdOutputNode):
                self.output_nodes.append(node)

    def searchInputNodes(self):
        for node in self.scene.nodes:
            if isinstance(node, StdInputNode):
                self.input_nodes.append(node)

    def render(self, audio_features=None):
        if len(self.output_nodes) == 0:
            self.searchOutputNodes()
        # Logic when the screen node is remove (he is not destroyed...)
        else:
            textures = list()
            for node in self.output_nodes:
                textures.append(node.render(audio_features))
        return textures

    def initGraphScene(self):
        self.replaceScreenNodes()
        self.searchOutputNodes()
        for node in self.scene.nodes:
            if isinstance(node, StdOutputNode):
                node.eval()
        self.searchInputNodes()

    def replaceScreenNodes(self):
        for node in self.scene.nodes:
            if isinstance(node, ScreenNode):
                output_node = StdOutputNode(self.scene)
                end_socket = node.inputs[0]
                edge = end_socket.edges[0]
                edge.reconnect(edge.end_socket, output_node.inputs[0])
                edge.updatePositions()
                self.scene.removeNode(node)

    def setTitle(self):
        self.title = self.getUserFriendlyFilename()
        super().setTitle()

    def getInputNodes(self):
        return self.input_nodes

    def hasInputNodes(self):
        return bool(len(self.input_nodes))
