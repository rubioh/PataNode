import os
import sys
import cv2
import time
import numpy as np

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from pyqtgraph import PlotWidget, plot, mkPen, GraphicsLayoutWidget

from audio.audio_pipeline import AudioEngine
from nodeeditor.utils import dumpException

DEBUG = True



class AudioLogWidget(QWidget):
    def __init__(self, audio_engine=None, parent=None):
        super().__init__(parent)

        self.title = 'Audio Features Logger'

        self.audio_engine = audio_engine
        self.log_buffer_size = self.audio_engine.log_buffer_size

        self._fps_timer = 30

        self.graphs = {}

        self.time = [0]*self.log_buffer_size
        self.data = [0]*self.log_buffer_size

        self.initUI()

    @property
    def fps_timer(self):
        return self._fps_timer
    @fps_timer.setter
    def fps_timer(self, value):
        self._fps_timer = value

        
    def setData(self):
        data1 = self.audio_engine.logger.information["smooth_low"]
        if len(data1) != self.audio_engine.logger.log_buffer_size+1:
            self.time = [i/self.fps_timer for i in range(len(data1))]

        #update graph
        for name, graph in self.graphs.items():
            data = self.audio_engine.logger.information[name]
            graph.clear()
            graph.plot(self.time, data, pen=self.pen)

    def setHidden(self, value):
        if not value:
            self.show()
            self.timer.start(int(1/self.fps_timer*1000))
            return
        self.hide()
        self.timer.stop()

    def initUI(self):
        self.setWindowTitle(self.title)
        self.setAcceptDrops(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor("#FF202020"))
        self.setPalette(p)

        # Main Layout
        self.mainLayout= QHBoxLayout(self)

        # List Box widget
        self.list_box = AudioFeaturesDragListBox(self.audio_engine.logger.information)
        self.mainLayout.addWidget(self.list_box)
        
        # Create graphics widget
        self.initGraphLayout()
        self.mainLayout.addWidget(self.graphLayout)
        self.initTimer()
        self.resize(self.height(),200)

    def initGraphLayout(self):
        self.graphLayout = GraphicsLayoutWidget()
        self.addGraph('smooth_low')

    def addGraph(self, name):
        if name not in self.graphs.keys():
            graph = self.graphLayout.addPlot()
            self.graphLayout.nextRow()
            self.graphLayout.setBackground((40,40,40,220))
            self.pen = mkPen(color=(255,40,40), width=2)
            #graph.setBackground((30,30,30,220)) 
            graph.setTitle(name.capitalize().replace("_", " "), color="w", size="10pt")
            graph.showGrid(x=True, y=True)                      
            graph.addLegend()           
            self.graphs[name] = graph

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pass
            pos = event.pos()
            selected_graph = None
            for name, graph in self.graphs.items():
                if self.getGraphItemFromPos(pos, graph):
                    selected_graph = graph
                    selected_name = name
            if selected_graph is not None:
                self.removeGraph(selected_graph, selected_name)

    def getGraphItemFromPos(self, pos, graph):
        gpos = graph.pos()
        gwidth = graph.width()
        gheight = graph.height()
        if pos.x()>gpos.x() and pos.x()<gpos.x()+graph.width():
            if pos.y()>gpos.y() and pos.y()<gpos.y()+graph.height():
                return True
        return False

    def removeGraph(self, graph, name):
        self.removeGraphFromLayout(graph)
        del self.graphs[name]

    def removeGraphFromLayout(self, graph):
        try:
            self.graphLayout.removeItem(graph)
        except:
            print('Failed to remove item', graph)
        #self.graphLayout.removeWidget(graph)

    def initTimer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.setData)
        self.timer.start(int(1/self.fps_timer*1000))

    def dragEnterEvent(self, e):
        e.accept()

    def dropEvent(self, event):
        if event.mimeData().hasFormat('application/x-item'):
            eventData = event.mimeData().data('application/x-item')
            dataStream = QDataStream(eventData, QIODevice.ReadOnly)
            text = dataStream.readQString()
            event.setDropAction(Qt.MoveAction)
            self.addGraph(text)
            event.accept()
        else:
            event.ignore()


class AudioFeaturesDragListBox(QListWidget):
    def __init__(self, features, parent=None):
        super().__init__(parent)
        self.keys = features.keys()
        self.initUI()

    def initUI(self):
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setResizeMode(True)
        self.setFixedWidth(120)
        
        stylesheet = os.path.join(os.path.dirname(__file__), "qss/qlistwidget-styl.qss")
        stylesheet = open(stylesheet, 'r').read()
        self.setStyleSheet(stylesheet)
        self.addMyItems()


    def addMyItems(self):
        keys = list(self.keys)
        keys.sort()
        for key in keys:
            self.addMyItem(key)

    def addMyItem(self, name):
        item = QListWidgetItem(name, self)
        item.setText(name)
        item.setForeground(QColor("#FFFFFF"))
        item.setSizeHint(QSize(16,16))
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
        item.setData(Qt.UserRole, name)

    def startDrag(self, *args, **kwargs):
        try:
            item = self.currentItem()
            
            item_data = item.data(Qt.UserRole)
            itemData = QByteArray()
            dataStream = QDataStream(itemData, QIODevice.WriteOnly)
            dataStream.writeQString(item.text())

            mimeData = QMimeData()
            mimeData.setData("application/x-item", itemData)

            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.exec_(Qt.MoveAction)
        except Exception as e:
            dumpException(e)


if __name__ == '__main__':
        app = QApplication(sys.argv)
        ae = AudioEngine()
        ae.start_recording()

        timer = QTimer()
        timer.timeout.connect(ae.__call__)
        timer.start(int(1/60*1000))


        ex = AudioLogWidget(ae)
        ex.show()
        
        sys.exit(app.exec())
