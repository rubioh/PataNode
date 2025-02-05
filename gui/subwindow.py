from PyQt5.QtCore import QDataStream, QIODevice, Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QAction, QGraphicsProxyWidget, QMenu

from nodeeditor.node_edge import EDGE_TYPE_DIRECT, EDGE_TYPE_BEZIER, EDGE_TYPE_SQUARE
from nodeeditor.node_editor_widget import NodeEditorWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode
from nodeeditor.node_graphics_view import MODE_EDGE_DRAG
from nodeeditor.utils import dumpException

from node.graph_container_node import GraphContainerNode
from node.node_conf import SHADER_NODES, get_class_from_opcode, LISTBOX_MIMETYPE
from node.shader_node_base import ShaderNode, Map
from program.output.screen.screen import ScreenNode


DEBUG = False
DEBUG_CONTEXT = False


class PataNodeSubWindow(NodeEditorWidget):
    def __init__(self, app=None):
        self.app = app
        self.light_engine = app.light_engine
        super().__init__()
#       self.setAttribute(Qt.WA_DeleteOnClose)

        self.setTitle()

        self.map_scene = app.map_scene

        self.setOpenGLSharedObject()

        self.initNewNodeActions()

        self.scene.addHasBeenModifiedListener(self.setTitle)
        self.scene.history.addHistoryRestoredListener(self.onHistoryRestored)
        self.scene.addDragEnterListener(self.onDragEnter)
        self.scene.addDropListener(self.onDrop)
        self.scene.setNodeClassSelector(self.getNodeClassFromData)
        self.scene.addItemSelectedListener(self.onSelected)

        self._close_event_listeners = []

        self.screen_node = None


    def searchScreenNodes(self):
        # TODO: better logic if multiple screen or output nodes
        for node in self.scene.nodes:
            if isinstance(node, ScreenNode):
                self.screen_node = node
                break

    def render(self, audio_features=None):
        if self.screen_node is None:
            self.searchScreenNodes()
        # Logic when the screen node is removed (it is not destroyed...)
        elif self.screen_node not in self.scene.nodes:
            self.searchScreenNodes()
        else:
            self.screen_node.render(audio_features)

    def getLastMainColors(self):
        if self.screen_node is not None:
            return self.screen_node.buffer_col
        else:
            return None

    def setOpenGLSharedObject(self):
        """
        Give the ctx reference to the scene
        """
        self.ctx = self.app.ctx
        self.scene.ctx = self.app.ctx
        self.scene.app = self.app
        self.scene.gl_widget = self.app.gl_widget
        self.scene.fbo_manager = self.app.gl_widget.fbo_manager

    def getNodeClassFromData(self, data):
        if "op_code" not in data:
            return None

        return get_class_from_opcode(data["op_code"])

    def doEvalOutputs(self):
        # Eval all output nodes
        for node in self.scene.nodes:
            if node.__class__.__name__ == "CalcNode_Output":
                node.eval()

    def onHistoryRestored(self):
        self.doEvalOutputs()

    def fileLoad(self, filename):
        if super().fileLoad(filename):
#           self.scene.fbo_manager.restoreFBOUsability()
            self.doEvalOutputs()
            return True

        return False

    def initNewNodeActions(self):
        self.node_actions = {}
        keys = list(SHADER_NODES.keys())
        keys.sort()

        for key in keys:
            node = SHADER_NODES[key]
            self.node_actions[node.op_code] = QAction(QIcon(node.icon), node.op_title)
            self.node_actions[node.op_code].setData(node.op_code)

    def initNodesContextMenu(self):
        context_menu = QMenu(self)
        keys = list(SHADER_NODES.keys())
        keys.sort()

        for key in keys:
            context_menu.addAction(self.node_actions[key])

        return context_menu

    def setTitle(self):
        self.setWindowTitle(self.getUserFriendlyFilename())

    def onSelected(self):
        items = self.getSelectedItems()
        item = items[0]

        if isinstance(item, QDMGraphicsNode):
            node = item.node
            self.updateInspector(node)

        if isinstance(item.node, Map):
            self.map_scene.reload_from_node(item.node)

    def updateInspector(self, node):
        self.app.updateInspector(node)

    def addCloseEventListener(self, callback):
        self._close_event_listeners.append(callback)

    def closeEvent(self, event):
        for callback in self._close_event_listeners:
            callback(self, event)

    def onDragEnter(self, event):
        if event.mimeData().hasFormat(LISTBOX_MIMETYPE):
            event.acceptProposedAction()
        else:
#           print(" ... denied drag enter event")
            event.setAccepted(False)

    def onDrop(self, event):
        if event.mimeData().hasFormat(LISTBOX_MIMETYPE):
            eventData = event.mimeData().data(LISTBOX_MIMETYPE)
            dataStream = QDataStream(eventData, QIODevice.ReadOnly)
            pixmap = QPixmap()
            dataStream >> pixmap
            op_code = dataStream.readInt()
            text = dataStream.readQString()
            mouse_position = event.pos()
            scene_position = self.scene.grScene.views()[0].mapToScene(mouse_position)

            if DEBUG:
                print(
                    "GOT DROP: [%d] '%s'" % (op_code, text),
                    "mouse:",
                    mouse_position,
                    "scene:",
                    scene_position,
                )

            try:
                node = get_class_from_opcode(op_code)(self.scene)

                if isinstance(node, GraphContainerNode):
                    node.setApp(self.app)

                node.setPos(scene_position.x(), scene_position.y())
                self.scene.history.storeHistory(
                    "Created node %s" % node.__class__.__name__
                )
            except Exception as e:
                dumpException(e)
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
#           print(" ... drop ignored, not requested format '%s'" % LISTBOX_MIMETYPE)
            event.ignore()

    def init_node(self, node_class):
        if node_class.__name__ == "MapLed2DNode":
            node = node_class(self.scene, self.light_engine)
        else:
            node = node_class(self.scene)
        return node

    def contextMenuEvent(self, event):
        try:
            item = self.scene.getItemAt(event.pos())

            if DEBUG_CONTEXT:
                print(item)

            if isinstance(item, QGraphicsProxyWidget):
                item = item.widget()

            if hasattr(item, "node") or hasattr(item, "socket"):
                self.handleNodeContextMenu(event)
            elif hasattr(item, "edge"):
                self.handleEdgeContextMenu(event)
#           elif item is None:
            else:
                self.handleNewNodeContextMenu(event)

            return super().contextMenuEvent(event)
        except Exception as e:
            dumpException(e)

    def handleNodeContextMenu(self, event):
        if DEBUG_CONTEXT:
            print("CONTEXT: NODE")

        selected = None
        item = self.scene.getItemAt(event.pos())

        if isinstance(item, QGraphicsProxyWidget):
            item = item.widget()

        if hasattr(item, "node"):
            selected = item.node
        if hasattr(item, "socket"):
            selected = item.socket.node

        context_menu = QMenu(self)
        markDirtyAct = context_menu.addAction("Mark Dirty")
        markDirtyDescendantsAct = context_menu.addAction("Mark Descendant Dirty")
        markInvalidAct = context_menu.addAction("Mark Invalid")
        unmarkInvalidAct = context_menu.addAction("Unmark Invalid")
        evalAct = context_menu.addAction("Eval")

        context_menu.addSeparator()

        if isinstance(selected, ShaderNode):
            reloadGLSLAct = context_menu.addAction("Reload glsl code")

        if isinstance(selected, ScreenNode):
            restoreFBOAct = context_menu.addAction("Restore FBOs dependencies")

        if isinstance(selected, ShaderNode):
            open_glsl_menu = context_menu.addMenu("Open glsl code")
            full_paths = selected.getGLSLCodePath()
            actOpenGLSL = []

            for path in full_paths:
                short_path = path.split("/")[-1]
                actOpenGLSL.append(open_glsl_menu.addAction(short_path))

        if isinstance(selected, GraphContainerNode):
            openSubWindow = context_menu.addAction("Open a new graph")

#       if selected and action == openGLSLAct:
#           selected.openGLSLCode()

#       openInspectorAct = context_menu.addAction("Open Parameters Inspector")

        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        if DEBUG_CONTEXT:
            print("got item:", selected)

        if selected and action == markDirtyAct:
            selected.markDirty()

        if selected and action == markDirtyDescendantsAct:
            selected.markDescendantsDirty()

        if selected and action == markInvalidAct:
            selected.markInvalid()

        if selected and action == unmarkInvalidAct:
            selected.markInvalid(False)

        if selected and action == evalAct:
            val = selected.eval()

            if DEBUG_CONTEXT:
                print("EVALUATED:", val)

        if isinstance(selected, ShaderNode) and action == reloadGLSLAct:
            selected.reloadGLSLCode()

        if isinstance(selected, ScreenNode) and action == restoreFBOAct:
            selected.restoreFBODependencies()

        if isinstance(selected, ShaderNode):
            for path, act in zip(full_paths, actOpenGLSL):
                if selected and action == act:
                    selected.openGLSLInTerminal(path)

        if isinstance(selected, GraphContainerNode) and action == openSubWindow:
            selected.openNewGraph()

    def handleEdgeContextMenu(self, event):
        if DEBUG_CONTEXT:
            print("CONTEXT: EDGE")

        context_menu = QMenu(self)
        bezierAct = context_menu.addAction("Bezier Edge")
        directAct = context_menu.addAction("Direct Edge")
        squareAct = context_menu.addAction("Square Edge")
        action = context_menu.exec_(self.mapToGlobal(event.pos()))
        selected = None
        item = self.scene.getItemAt(event.pos())

        if hasattr(item, "edge"):
            selected = item.edge

        if selected and action == bezierAct:
            selected.edge_type = EDGE_TYPE_BEZIER

        if selected and action == directAct:
            selected.edge_type = EDGE_TYPE_DIRECT

        if selected and action == squareAct:
            selected.edge_type = EDGE_TYPE_SQUARE

    # Helper functions
    def determine_target_socket_of_node(self, was_dragged_flag, new_calc_node):
        target_socket = None

        if was_dragged_flag:
            if len(new_calc_node.inputs) > 0:
                target_socket = new_calc_node.inputs[0]
        else:
            if len(new_calc_node.outputs) > 0:
                target_socket = new_calc_node.outputs[0]

        return target_socket

    def finish_new_node_state(self, new_calc_node):
        self.scene.doDeselectItems()
        new_calc_node.grNode.doSelect(True)
        new_calc_node.grNode.onSelected()

    def handleNewNodeContextMenu(self, event):
        if DEBUG_CONTEXT:
            print("CONTEXT: EMPTY SPACE")

        context_menu = self.initNodesContextMenu()
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        if action is not None:
            new_calc_node = get_class_from_opcode(action.data())(self.scene)
            scene_pos = self.scene.getView().mapToScene(event.pos())
            new_calc_node.setPos(scene_pos.x(), scene_pos.y())

            if DEBUG_CONTEXT:
                print("Selected node:", new_calc_node)

            if self.scene.getView().mode == MODE_EDGE_DRAG:
                # If we were dragging an edge...
                target_socket = self.determine_target_socket_of_node(
                    self.scene.getView().dragging.drag_start_socket.is_output,
                    new_calc_node,
                )

                if target_socket is not None:
                    self.scene.getView().dragging.edgeDragEnd(target_socket.grSocket)
                    self.finish_new_node_state(new_calc_node)
            else:
                self.scene.history.storeHistory("Created %s" % new_calc_node.__class__.__name__)
