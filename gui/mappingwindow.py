from qtpy.QtCore import Qt
from qtpy.QtWidgets import (  # , QDMGraphicsNode
    QAction,
    QDockWidget,
    QMainWindow,
    QVBoxLayout,
)

from gui.map.polydockwidget import PolyDockWidget
from gui.map.polygraphicscene import PolyGraphicScene
from gui.map.polygraphicview import PolyGraphicView
from node.node_conf import LISTBOX_MIMETYPE

DEBUG = False
DEBUG_CONTEXT = False


class PataNodeMappingWindow(QMainWindow):
    def __init__(self, app=None, mapping_program=None):
        self.app = app
        self.mapping_program = mapping_program
        super().__init__()
        self.setTitle()
        self.setOpenGLSharedObject()
        self.initNewNodeActions()
        self._close_event_listeners = []
        self.addAction(
            QAction(
                "&Map",
                self,
                shortcut="Ctrl+M",
                statusTip="Hide mapping window",
                triggered=self.hide,
            )
        )
        self.addAction(
            QAction(
                "E&xit",
                self,
                shortcut="Ctrl+Q",
                statusTip="Exit application",
                triggered=self.close,
            )
        )
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.init_polygon_widget()
        self.createPolyDock()

    def createPolyDock(self):
        self.nodesListWidget = PolyDockWidget(self.scene)

        self.nodesDock = QDockWidget("polies")
        self.nodesDock.setWidget(self.nodesListWidget)
        self.nodesDock.setFloating(False)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.nodesDock)
        self.resizeDocks((self.nodesDock,), (220,), Qt.Horizontal)

    def init_polygon_widget(self):
        self.scene = PolyGraphicScene()
        self.view = PolyGraphicView(self.scene, self)
        self.setCentralWidget(self.view)

    def setOpenGLSharedObject(self):
        pass

    def hasSelectedItems(self):
        return False

    def fileLoad(self, filename):
        pass

    def initNewNodeActions(self):
        pass

    def setTitle(self):
        self.setWindowTitle("Mapping")

    def onSelected(self):
        pass

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
        pass

    def contextMenuEvent(self, event):
        pass

    def updateMapping(self, wireframe: bool, polygons: list):
        new_polys = [0] * len(polygons)

        for i in range(len(polygons)):
            new_poly = []
            for j in range(len(polygons[i]) // 2):
                new_poly.append(polygons[i][j * 2])
                new_poly.append(polygons[i][j * 2 + 1])
                new_poly.append(self.mapping.base_polygons[0][j * 4 + 2])
                new_poly.append(self.mapping.base_polygons[0][j * 4 + 3])
            polygons[i] = new_poly

        for i in range(len(polygons) // 2):
            new_polys[i * 2] = polygons[i]
            new_polys[i * 2 + 1] = polygons[i + len(polygons) // 2]
        polygons = new_polys

        self.mapping_program.wireframe = wireframe
        self.mapping_program.updatePolygons(polygons)
        self.mapping_program.updateMapping(wireframe, polygons)
