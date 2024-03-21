import os, sys
from PyQt5.QtWidgets import QApplication
import program.program_conf

#sys.path.insert(0, os.path.join( os.path.dirname(__file__), "..", ".." ))
#from app import PataShade
from app import PataShade
#from window import Window, WindowSize
#from glcontext import GLWindow, MGLW, QModernGLWidget

if __name__ == '__main__':

    # print(QStyleFactory.keys())
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    patanode = PataShade()
    patanode.show()

    sys.exit(app.exec_())
