from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

#from nodeeditor.utils import dumpException

#from node.node_conf import SHADER_NODES, get_class_from_opcode, LISTBOX_MIMETYPE


class QDMInspector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        grid = QVBoxLayout()
        grid.insertStretch(-1,1)
        self.grid = grid
        self.setLayout(grid)

    def addLayout(self, obj_connect=None): # TODO Redraw Layout at each onSelected -> Node
        for name, properties in obj_connect.items():
            self.grid.addWidget(self.createWidget(properties))
        self.grid.insertStretch(-1,1)

    def createWidget(self, properties):
        if properties["widget"] == 0:
            return self.createSlider(properties)

    def createSlider(self, properties):
        name = properties["name"].lower().capitalize()
        groupBox = QGroupBox(name)
        slider = QSlider(Qt.Horizontal)
        slider.setFocusPolicy(Qt.StrongFocus)
        slider.setTickPosition(QSlider.TicksBothSides)
        slider.setTickInterval(10)
        slider.setMinimum(0)
        slider.setMaximum(100)

        value = properties["value"]
        minmax_range = properties["maximum"] - properties["minimum"]
        value = (value - properties["minimum"])/minmax_range
        slider.setValue(int(value*100))
        slider.setSingleStep(1)
        
        connect = properties["connect"]
        fine_connect = lambda v : connect(v/100.*minmax_range + properties["minimum"])
        slider.valueChanged.connect(fine_connect)

        vbox = QVBoxLayout()
        vbox.addWidget(slider)
        vbox.addStretch(1)
        groupBox.setLayout(vbox)
        groupBox.setFlat(True)
        return groupBox

    def clearLayout(self):
        while self.grid.count():
            child = self.grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def updateParametersToSelectedItems(self, obj):
        self.clearLayout()
        obj_connect = obj.getAdaptableParameters()
        self.addLayout(obj_connect)

    def onSelectionChanged(self, value):
        self.clearLayout()
        self.addLayout()


