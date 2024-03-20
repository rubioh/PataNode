import os, sys
from qtpy.QtWidgets import QApplication

sys.path.insert(0, os.path.join( os.path.dirname(__file__), "..", ".." ))

from app import PataShade
from node.patanode import PataNode


if __name__ == '__main__':

    # print(QStyleFactory.keys())
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    patanode = PataShade()
    patanode.show()

    sys.exit(app.exec_())
