from PyQt5.QtGui import QPixmap, QIcon, QDrag
from PyQt5.QtCore import QSize, Qt, QByteArray, QDataStream, QMimeData, QIODevice, QPoint
from PyQt5.QtWidgets import QListWidget, QAbstractItemView, QListWidgetItem

from nodeeditor.utils import dumpException

from node.node_conf import SHADER_NODES, get_class_from_opcode, LISTBOX_MIMETYPE


class QDMInspector(QListWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()


    def initUI(self):
        # init
        self.setIconSize(QSize(32, 32))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
    
