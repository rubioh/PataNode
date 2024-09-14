from PyQt5.QtGui import QPixmap, QIcon, QDrag, QColor
from PyQt5.QtCore import QSize, Qt, QByteArray, QDataStream, QMimeData, QIODevice, QPoint
from PyQt5.QtWidgets import QListWidget, QAbstractItemView, QListWidgetItem, QTreeWidget, QTreeWidgetItem
from PyQt5.Qt import *

from nodeeditor.utils import dumpException

from node.node_conf import AUDIO_NODES, SHADER_NODES, get_class_from_opcode, LISTBOX_MIMETYPE
from node.graph_container_node import GraphContainerNode

class QDMDragListbox(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        # init
        self.setColumnCount(2)
        self.setHeaderLabels(["Node types", "Name"])
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)

        self.addShaderNodes()
        #self.addAudioNodes()
        self.addContainerNodes()


    def addShaderNodes(self):
        keys = list(SHADER_NODES.keys())
        keys.sort()
        
        shader_types = {}
        for key in keys:
            node = get_class_from_opcode(key)
            node_type_reference = node.node_type_reference
            if node_type_reference in shader_types.keys():
                shader_types[node_type_reference].append((node.op_title, node.icon, node.op_code))
            else:
                shader_types[node_type_reference] = list()
                shader_types[node_type_reference].append((node.op_title, node.icon, node.op_code))
        
        for shader_type in shader_types:
            shader_type_item = QTreeWidgetItem(self)
            shader_type_item.setText(0, shader_type)
            shader_type_item.setForeground(0, QColor("#E39600"))
            for data in shader_types[shader_type]:
                self.addMyItem(*data, shader_type_item)
            shader_type_item.setChildIndicatorPolicy(0)
            shader_type_item.sortChildren(1, Qt.AscendingOrder)
        self.sortItems(0, Qt.AscendingOrder)

    def addAudioNodes(self):
        keys = list(AUDIO_NODES.keys())
        keys.sort()
        audio_type_item = QTreeWidgetItem(self)
        audio_type_item.setText(0, "Audio Features Transform")
        audio_type_item.setForeground(0, QColor("#E39600"))
        for key in keys:
            node = get_class_from_opcode(key)
            self.addMyItem(node.op_title, node.icon, node.op_code, audio_type_item)
        audio_type_item.setChildIndicatorPolicy(0)
        audio_type_item.sortChildren(1, Qt.AscendingOrder)

        self.sortItems(0, Qt.AscendingOrder)

    def addContainerNodes(self):
        container_type_item = QTreeWidgetItem(self)
        container_type_item.setText(0, "Container")
        container_type_item.setForeground(0, QColor("#D38600"))
        node = GraphContainerNode
        self.addMyItem(node.op_title, node.icon, node.op_code, container_type_item)

        container_type_item.setChildIndicatorPolicy(0)
        container_type_item.sortChildren(1, Qt.AscendingOrder)

    def addMyItem(self, name, icon=None, op_code=0, parent=None):
        item = QTreeWidgetItem(parent) # can be (icon, text, parent, <int>type)

        #qname.setTextColor()
        item.setText(1, name)
        item.setForeground(1, QColor("#BAC18A"))
        pixmap = QPixmap(icon if icon is not None else ".")
        item.setIcon(1, QIcon(pixmap))
        item.setSizeHint(1, QSize(16, 16))

        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
        # setup data
        item.setData(1, Qt.UserRole, pixmap)
        item.setData(1, Qt.UserRole + 1, op_code)
        #item.setHidden()

    def startDrag(self, *args, **kwargs):
        try:
            item = self.currentItem()
            if item.text(0):
                return
            op_code = item.data(1, Qt.UserRole + 1)

            pixmap = QPixmap(item.data(1, Qt.UserRole))


            itemData = QByteArray()
            dataStream = QDataStream(itemData, QIODevice.WriteOnly)
            dataStream << pixmap
            dataStream.writeInt(op_code)
            dataStream.writeQString(item.text(1))

            mimeData = QMimeData()
            mimeData.setData(LISTBOX_MIMETYPE, itemData)

            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
            drag.setPixmap(pixmap)

            drag.exec_(Qt.MoveAction)

        except Exception as e: dumpException(e)
