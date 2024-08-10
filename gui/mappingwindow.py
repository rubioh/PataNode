import os
from qtpy.QtCore import Qt
from qtpy.QtGui import QBrush, QPen, QFont, QColor, QPolygonF
from qtpy.QtWidgets import QWidget, QVBoxLayout, QApplication, QMessageBox, QLabel, QGraphicsItem, QTextEdit, QPushButton, QAction, QMainWindow
import os
import time
import threading
from nodeeditor.node_scene import Scene, InvalidFile
from gui.map.polygraphicscene import PolyGraphicScene
from gui.map.polygraphicview import PolyGraphicView
from gui.map.polydockwidget import *

DEBUG = False
DEBUG_CONTEXT = False

class PataNodeMappingWindow(QMainWindow):
    def __init__(self, app=None):
        self.app = app
        super().__init__()
        self.setTitle()
        self.setOpenGLSharedObject()
        self.initNewNodeActions()
        self._close_event_listeners = []
        self.addAction(QAction('&Map', self, shortcut='Ctrl+M', statusTip="Hide mapping window", triggered=self.hide))
        self.addAction(QAction('E&xit', self, shortcut='Ctrl+Q', statusTip="Exit application", triggered=self.close))
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
        items = self.getSelectedItems()
        item = items[0]
        if isinstance(item, QDMGraphicsNode):
            node = item.node
            self.updateInspector(node)

    def updateInspector(self, node):
        self.app.updateInspector(node)

    def addCloseEventListener(self, callback):
        self._close_event_listeners.append(callback)

    def closeEvent(self, event):
        for callback in self._close_event_listeners: callback(self, event)

    def onDragEnter(self, event):
        if event.mimeData().hasFormat(LISTBOX_MIMETYPE):
            event.acceptProposedAction()
        else:
            # print(" ... denied drag enter event")
            event.setAccepted(False)

    def onDrop(self, event):
        pass

    def contextMenuEvent(self, event):
        pass

