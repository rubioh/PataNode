# -*- coding: utf-8 -*-
"""
A module containing Graphic representation of :class:`~nodeeditor.node_scene.Scene`
"""
import math
from qtpy.QtWidgets import QGraphicsScene, QWidget
from qtpy.QtCore import Signal, QRect, QLine, Qt, QPointF, QLineF
from qtpy.QtGui import QColor, QPen, QFont, QPainter, QBrush, QPolygonF, QDragEnterEvent, QDropEvent, QMouseEvent, QKeyEvent, QWheelEvent, QPainterPath

from nodeeditor.utils import dumpException
from nodeeditor.node_graphics_view import STATE_STRING, DEBUG_STATE

class mapPoint(QPointF):
    def __init__(self, x, y, tx, ty):
        super().__init__(x, y)
        self.tx = tx
        self.ty = ty

class PolyProxy():
    def __init__(self):
        hrx = 1280 / 2
        hry = 720 / 2
        xe = hrx
        ye = hry
        xs = -hrx
        ys = -hry

        self.pointlist = [mapPoint(xs, ys, 0., 0.), mapPoint(xs, ye, 0., 1.), 
                mapPoint(xe, ye, 1., 1.), mapPoint(xe, ys, 1., 0.), mapPoint(xs, ys, 0., 0.)]
        self.point_drag_idx = None
        self.selected_point_idx = None
        self.selected_line_idx = None

class PolyGraphicScene(QGraphicsScene):
    """Class representing Graphic of :class:`~nodeeditor.node_scene.Scene`"""
    #: pyqtSignal emitted when some item is selected in the `Scene`
    itemSelected = Signal()
    #: pyqtSignal emitted when items are deselected in the `Scene`
    itemsDeselected = Signal()

    def __init__(self):
        """
        :param scene: reference to the :class:`~nodeeditor.node_scene.Scene`
        :type scene: :class:`~nodeeditor.node_scene.Scene`
        :param parent: parent widget
        :type parent: QWidget
        """
        super().__init__(None)

        self.scene = "scene"

        # There is an issue when reconnecting edges -> mouseMove and trying to delete/remove them
        # the edges stayed in the scene in Qt, however python side was deleted
        # this caused a lot of troubles...
        #
        # I've spend months to find this sh*t!!
        #
        # https://bugreports.qt.io/browse/QTBUG-18021
        # https://bugreports.qt.io/browse/QTBUG-50691
        # Affected versions: 4.7.1, 4.7.2, 4.8.0, 5.5.1, 5.7.0 - LOL!
        self.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.poly_drag_idx = None
        # settings
        self.gridSize = 20
        self.gridSquares = 5
        self._pen = QPen(Qt.white)
        self._pen.setWidthF(2.0)
        self._pen.setStyle(Qt.SolidLine)
        self.initAssets()
        self.setBackgroundBrush(self._color_background)
        self.selected_poly_idx = 0
        self.polyproxies = [PolyProxy()]

    def initAssets(self):
        """Initialize ``QObjects`` like ``QColor``, ``QPen`` and ``QBrush``"""
        self._color_background = QColor("#393939")
        self._color_light = QColor("#2f2f2f")
        self._color_dark = QColor("#292929")
        self._color_state = QColor("#ccc")

        self._pen_light = QPen(self._color_light)
        self._pen_light.setWidth(1)
        self._pen_dark = QPen(self._color_dark)
        self._pen_dark.setWidth(2)

        self._pen_state = QPen(self._color_state)
        self._font_state = QFont("Ubuntu", 16)

    # the drag events won't be allowed until dragMoveEvent is overriden
    def dragMoveEvent(self, event):
        """Overriden Qt's dragMoveEvent to enable Qt's Drag Events"""
        pass

    def setGrScene(self, width: int, height: int):
        """Set `width` and `height` of the `Graphics Scene`"""
        self.setSceneRect(-width // 2, -height // 2, width, height)

    def drawPolys(self, painter):
        pen = QPen(Qt.white)
#        pen.setWidthF(2.0)
 #       pen.setStyle(Qt.SolidLine)

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        brush = QBrush(QColor.fromRgbF(.8, .8, .8, .4))
        brush.setStyle(Qt.BDiagPattern)
        path = QPainterPath()
        path.addPolygon(QPolygonF(self.polyproxies[self.selected_poly_idx].pointlist))
        painter.fillPath(path, brush);

        plframe = PolyProxy().pointlist
        painter.setPen(Qt.yellow)
        for p1, p2 in zip(plframe[:-1], plframe[1:]):
            painter.drawLine(QLineF(p1, p2))

        
        for i, poly in enumerate(self.polyproxies):
            painter.setPen(Qt.white)
            j = 0
            pl = poly.pointlist
            for p1, p2 in zip(pl[:-1], pl[1:]):
                if j == self.polyproxies[self.selected_poly_idx].selected_line_idx and i == self.selected_poly_idx:
                    painter.setPen(Qt.blue)
                painter.drawLine(QLineF(p1, p2))
                painter.setPen(Qt.white)
                j = j + 1

            pen = QPen(Qt.red)
            pen.setWidthF(10.0)
            painter.setPen(pen)
            for p in pl:
                painter.drawPoint(p)

    def mousePressEvent(self, event: QMouseEvent):
        """Dispatch Qt's mouseRelease event to corresponding function below"""
        if event.button() == Qt.LeftButton:
            self.leftclickevent(event)
        else:
            super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        pl = self.getcurrentpoly().pointlist
        pd = self.getcurrentpoly().point_drag_idx
        if pd != None:
            pl[pd] = mapPoint(event.scenePos().x(), event.scenePos().y(), pl[pd].tx, pl[pd].ty) 
            if pd == 0:
                pl[len(pl) - 1] = mapPoint(pl[0].x(), pl[0].y(), pl[0].tx,pl[0].ty)
            if pd == len(pl) - 1:
                u = len(pl) - 1
                pl[0] = mapPoint(pl[u].x(), pl[u].y(), pl[u].tx,pl[u].ty)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.getcurrentpoly().point_drag_idx = None

    def dd(self, p1, p2):
        x = p2.x()-p1.x()
        y = p2.y()-p1.y()
        return math.sqrt(x*x+y*y)

    def dot(self, p1, p2):
        return (p1.x()*p2.x())+(p1.y()*p2.y())

    def line_intersection(self, p1, p2, clickpos):
        p = p2-p1
        cp = clickpos - p1
        d = max(0., min(1., (self.dot(cp, p) / self.dot(p, p))))
        proj = p1 + p * d
        return (self.dd(proj, clickpos) < 5.)

    def subdivide(self, line_idx):
        p1 = self.getcurrentpoly().pointlist[line_idx]
        p2 = self.getcurrentpoly().pointlist[line_idx+1]
        newp = (p1 + p2) / 2 
        newp.tx = (p1.tx + p2.tx) / 2
        newp.ty = (p1.ty + p2.ty) / 2
        self.getcurrentpoly().pointlist.insert(line_idx+1, newp)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_S and self.getcurrentpoly().selected_line_idx != None:
            self.subdivide(self.getcurrentpoly().selected_line_idx)
            self.getcurrentpoly().selected_line_idx = None
        if event.key() == Qt.Key_R:
            self.polyproxies = [PolyProxy()]
            self.selected_poly_idx = 0

        if event.key() == Qt.Key_P:
            self.polyproxies.append(PolyProxy())

        if event.key() == Qt.Key_N:
            self.selected_poly_idx += 1
            self.selected_poly_idx %= len(self.polyproxies)

        self.update()
#        self.selected_point_idx = None
#        self.selected_line_idx = None
#        self.selected_poly_idx = None

    def getcurrentpoly(self):
        return self.polyproxies[self.selected_poly_idx]

    def leftclickevent(self, event):
        self.getcurrentpoly().selected_line_idx = None
        self.poly_drag_idx = None
        poly = QPolygonF(self.getcurrentpoly().pointlist)
        for i, point in enumerate(self.getcurrentpoly().pointlist):
            if self.dd(point, event.scenePos()) < 5.:
                self.getcurrentpoly().point_drag_idx = i
                return
        i = 0
        for p1, p2 in zip(self.getcurrentpoly().pointlist[0:-1], self.getcurrentpoly().pointlist[1:]):
            if self.line_intersection(p1, p2, event.scenePos()):
                self.getcurrentpoly().selected_line_idx = i
                return
            i=i+1
        if poly.containsPoint(event.scenePos(), Qt.OddEvenFill):
            self.poly_drag_idx = self.selected_poly_idx

    def drawBackground(self, painter:QPainter, rect:QRect):
        """Draw background scene grid"""
        super().drawBackground(painter, rect)

        # here we create our grid
        left = int(math.floor(rect.left()))
        right = int(math.ceil(rect.right()))
        top = int(math.floor(rect.top()))
        bottom = int(math.ceil(rect.bottom()))

        first_left = left - (left % self.gridSize)
        first_top = top - (top % self.gridSize)

        # compute all lines to be drawn
        lines_light, lines_dark = [], []
        for x in range(first_left, right, self.gridSize):
            if (x % (self.gridSize*self.gridSquares) != 0): lines_light.append(QLine(x, top, x, bottom))
            else: lines_dark.append(QLine(x, top, x, bottom))

        for y in range(first_top, bottom, self.gridSize):
            if (y % (self.gridSize*self.gridSquares) != 0): lines_light.append(QLine(left, y, right, y))
            else: lines_dark.append(QLine(left, y, right, y))


        # draw the lines
        painter.setPen(self._pen_light)
        try: painter.drawLines(*lines_light)                    # supporting PyQt5
        except TypeError: painter.drawLines(lines_light)        # supporting PySide2

        painter.setPen(self._pen_dark)
        try: painter.drawLines(*lines_dark)                     # supporting PyQt5
        except TypeError: painter.drawLines(lines_dark)         # supporting PySide2

        if DEBUG_STATE:
            try:
                painter.setFont(self._font_state)
                painter.setPen(self._pen_state)
                painter.setRenderHint(QPainter.TextAntialiasing)
                offset = 14
                rect_state = QRect(rect.x()+offset, rect.y()+offset, rect.width()-2*offset, rect.height()-2*offset)
                painter.drawText(rect_state, Qt.AlignRight | Qt.AlignTop, STATE_STRING[self.views()[0].mode].upper())
            except: dumpException()
        self.drawPolys(painter)