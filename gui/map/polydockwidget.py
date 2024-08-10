from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.Qt import *


class PolyDockWidget(QWidget):
    def __init__(self, polyscene, parent=None):
        super().__init__(parent)
        self.scene = polyscene
        self.initUI()

    def initUI(self):
        grid = QVBoxLayout()
        grid.insertStretch(-1,-1)
        self.grid = grid
        source_select = QComboBox()
        source_select.addItems(["Source 1", "Source 2", "Source 3"])
        grid.addWidget(source_select)
        type_select = QComboBox()
        type_select.addItems(["fit", "crop", "mask"])
        grid.addWidget(type_select)
        self.setLayout(grid)

    def get_current_data(self):
    	return self.scene.polyproxies