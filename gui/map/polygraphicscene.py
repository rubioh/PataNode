# -*- coding: utf-8 -*-

"""
A module containing Graphic representation of :class:`~nodeeditor.node_scene.Scene`
"""

import copy
import math

from qtpy.QtCore import Signal, QRect, QLine, Qt, QPointF, QLineF
from qtpy.QtGui import (
    QColor,
    QPen,
    QFont,
    QPainter,
    QBrush,
    QPolygonF,
    QMouseEvent,
    QKeyEvent,
    QPainterPath,
)
from qtpy.QtWidgets import QGraphicsScene

from nodeeditor.utils import dumpException
from nodeeditor.node_graphics_view import DEBUG_STATE, STATE_STRING


class mapPoint(QPointF):
    def __init__(self, x, y, tx, ty, edge=None):
        super().__init__(x, y)
        self.tx = tx
        self.ty = ty
        self.edge = edge

    def __deepcopy__(self, memo):
        return mapPoint(self.x(), self.y(), self.tx, self.ty, self.edge)


class PolyProxy:
    def from_poly(self, polys):
        self.pointlist = []

        if len(polys) < 4:
            return

        for i in range(len(polys) // 4):
            self.pointlist.append(
                mapPoint(
                    polys[i * 4] * self.hrx - self.hrx / 2.0,
                    polys[i * 4 + 1] * self.hry - self.hry / 2.0,
                    polys[i * 4 + 2],
                    polys[i * 4 + 3],
                    i,
                )
            )

        self.pointlist.append(
            mapPoint(
                polys[0] * self.hrx - self.hrx / 2.0,
                polys[1] * self.hry - self.hry / 2.0,
                polys[2],
                polys[3],
                4,
            )
        )

    def to_polys(self):
        ret = []

        for p in self.pointlist:
            ret.append((p.x() + self.hrx / 2.0) / (self.hrx))
            ret.append((p.y() + self.hry / 2.0) / (self.hry))
            ret.append(p.tx)
            ret.append(p.ty)

        ret.pop()
        return ret

    def __init__(self):
        hrx = 1280 / 2
        hry = 720 / 2
        xe = hrx
        ye = hry
        xs = -hrx
        ys = -hry
        self.hrx = hrx * 2.0
        self.hry = hry * 2.0

        self.translation = QPointF(0.0, 0.0)
        self.pointlist = [
            mapPoint(xs, ys, 0.0, 0.0, 0),
            mapPoint(xs, ye, 0.0, 1.0, 1),
            mapPoint(xe, ye, 1.0, 1.0, 2),
            mapPoint(xe, ys, 1.0, 0.0, 3),
            mapPoint(xs, ys, 0.0, 0.0, 4),
        ]
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
        self.rotate = False
        self.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.poly_drag_idx = None

        # Settings
        self.gridSize = 20
        self.gridSquares = 5
        self._pen = QPen(Qt.white)
        self._pen.setWidthF(2.0)
        self._pen.setStyle(Qt.SolidLine)
        self.initAssets()
        self.dragged_poly_idx = None
        self.program = None
        self.setBackgroundBrush(self._color_background)
        self.selected_poly_idx = 0
        self.polyproxies = [PolyProxy(), PolyProxy()]

    def fromPolygons(self, polygons):
        self.polyproxies = []
        for p in polygons:
            n = PolyProxy()
            n.from_poly(p)
            self.polyproxies.append(n)

    def makePolygons(self):
        return [p.to_polys() for p in self.polyproxies]
        #       scisor_id = 0
        polyproxies = copy.deepcopy(self.polyproxies)
        for poly, scisor in zip(polyproxies[::2], polyproxies[1::2]):
            current_scisor_idx = 0
            next_line_idx = 1
            current_line_idx = 0
            while current_scisor_idx != 4:
                while poly.pointlist[next_line_idx].edge is None:
                    next_line_idx = next_line_idx + 1

                p = poly.pointlist[current_line_idx]
                poly.pointlist[current_line_idx] = mapPoint(
                    p.x(),
                    p.y(),
                    (
                        (scisor.pointlist[current_scisor_idx].x() + scisor.hrx / 2.0)
                        / scisor.hrx
                    ),
                    (
                        (scisor.pointlist[current_scisor_idx].y() + scisor.hry / 2.0)
                        / scisor.hry
                    ),
                )

                for j in range(current_line_idx, next_line_idx):
                    pass  # FIXME: ???

                current_scisor_idx = current_scisor_idx + 1
                current_line_idx = next_line_idx
                next_line_idx = current_line_idx + 1

        return [p.to_polys() for p in polyproxies]

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

    # The drag events won't be allowed until dragMoveEvent is overriden
    def dragMoveEvent(self, event):
        """Overriden Qt's dragMoveEvent to enable Qt's Drag Events"""
        pass

    def setGrScene(self, width: int, height: int):
        """Set `width` and `height` of the `Graphics Scene`"""
        self.setSceneRect(-width // 2, -height // 2, width, height)

    def drawPolys(self, painter):
        if self.program is not None:
            self.program.updatePolygons(self.makePolygons())
        pen = QPen(Qt.white)
        #       pen.setWidthF(2.0)
        #       pen.setStyle(Qt.SolidLine)

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        brush = QBrush(QColor.fromRgbF(0.8, 0.8, 0.8, 0.4))
        brush.setStyle(Qt.BDiagPattern)
        path = QPainterPath()
        path.addPolygon(QPolygonF(self.polyproxies[self.selected_poly_idx].pointlist))
        painter.fillPath(path, brush)

        plframe = PolyProxy().pointlist
        painter.setPen(Qt.black)
        for p1, p2 in zip(plframe[:-1], plframe[1:]):
            painter.drawLine(QLineF(p1, p2))

        for i, poly in enumerate(self.polyproxies):
            painter.setPen(Qt.white)
            j = 0
            pl = poly.pointlist
            for p1, p2 in zip(pl[:-1], pl[1:]):
                if i % 2 == 1:
                    painter.setPen(Qt.red)
                if i == self.selected_poly_idx:
                    painter.setPen(Qt.yellow)
                if (
                    j == self.polyproxies[self.selected_poly_idx].selected_line_idx
                    and i == self.selected_poly_idx
                ):
                    painter.setPen(Qt.blue)
                painter.drawLine(QLineF(p1, p2))
                painter.setPen(Qt.white)
                j = j + 1

            pen = QPen(Qt.red)
            pen.setWidthF(10.0)
            painter.setPen(pen)
            for p in pl:
                painter.drawPoint(p)

    def reload_from_node(self, node):
        self.program = node.program
        self.fromPolygons(node.program.polygons)
        self.selected_poly_idx = 0

    def mousePressEvent(self, event: QMouseEvent):
        """Dispatch Qt's mouseRelease event to corresponding function below"""
        if event.button() == Qt.LeftButton:
            self.leftclickevent(event)
        else:
            super().mouseReleaseEvent(event)

    def do_rotate(self, diffx, diffy):
        diff = (diffy) / 300.0
        poly = self.getcurrentpoly()
        pl = self.getcurrentpoly().pointlist

        for i, p in enumerate(self.getcurrentpoly().pointlist):
            n_p = (
                ((p.x() - poly.hrx / 2.0) + poly.hrx / 2.0) / poly.hrx,
                ((p.y() - poly.hry / 2.0) + poly.hry / 2.0) / poly.hry,
            )
            x = n_p[0] * math.cos(diff) + n_p[1] * -math.sin(diff)
            y = n_p[0] * math.sin(diff) + n_p[1] * math.cos(diff)
            x = x * poly.hrx - poly.hrx / 2 + poly.hrx / 2.0
            y = y * poly.hry - poly.hry / 2 + poly.hry / 2.0
            pl[i] = mapPoint(x, y, p.tx, p.ty, p.edge)

    def mouseMoveEvent(self, event):
        pl = self.getcurrentpoly().pointlist
        pd = self.getcurrentpoly().point_drag_idx

        if self.rotate:
            self.do_rotate(
                event.scenePos().x() - event.lastScenePos().x(),
                event.scenePos().y() - event.lastScenePos().y(),
            )

        if self.poly_drag_idx is not None:
            for i, p in enumerate(pl):
                pl[i] = mapPoint(
                    p.x() + (event.scenePos().x() - event.lastScenePos().x()),
                    p.y() + (event.scenePos().y() - event.lastScenePos().y()),
                    p.tx,
                    p.ty,
                    p.edge,
                )

        if pd is not None:
            pl[pd] = mapPoint(
                event.scenePos().x(),
                event.scenePos().y(),
                pl[pd].tx,
                pl[pd].ty,
                pl[pd].edge,
            )

            if pd == 0:
                pl[len(pl) - 1] = mapPoint(
                    pl[0].x(), pl[0].y(), pl[0].tx, pl[0].ty, pl[0].edge
                )

            if pd == len(pl) - 1:
                u = len(pl) - 1
                pl[0] = mapPoint(pl[u].x(), pl[u].y(), pl[u].tx, pl[u].ty, pl[u].edge)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.getcurrentpoly().point_drag_idx = None
        self.poly_drag_idx = None

    def dd(self, p1, p2):
        x = p2.x() - p1.x()
        y = p2.y() - p1.y()
        return math.sqrt(x * x + y * y)

    def dot(self, p1, p2):
        return (p1.x() * p2.x()) + (p1.y() * p2.y())

    def line_intersection(self, p1, p2, clickpos):
        p = p2 - p1
        cp = clickpos - p1
        d = max(0.0, min(1.0, (self.dot(cp, p) / self.dot(p, p))))
        proj = p1 + p * d
        return self.dd(proj, clickpos) < 5.0

    def subdivide(self, line_idx):
        p1 = self.getcurrentpoly().pointlist[line_idx]
        p2 = self.getcurrentpoly().pointlist[line_idx + 1]
        newp = (p1 + p2) / 2
        newp.tx = (p1.tx + p2.tx) / 2
        newp.ty = (p1.ty + p2.ty) / 2
        self.getcurrentpoly().pointlist.insert(
            line_idx + 1, mapPoint(newp.x(), newp.y(), newp.tx, newp.ty)
        )

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_F:
            self.rotate = False

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_S and self.getcurrentpoly().selected_line_idx != None:
            self.subdivide(self.getcurrentpoly().selected_line_idx)
            self.getcurrentpoly().selected_line_idx = None

        if event.key() == Qt.Key_R:
            self.polyproxies = [PolyProxy(), PolyProxy()]
            self.selected_poly_idx = 0

        if event.key() == Qt.Key_W:
            if self.program:
                self.program.wireframe = not self.program.wireframe

        if event.key() == Qt.Key_H:
            for i, p in enumerate(self.getcurrentpoly().pointlist):
                pl = self.getcurrentpoly().pointlist[i]
                self.getcurrentpoly().pointlist[i] = mapPoint(
                    pl.x() / 1.1892, pl.y() / 1.1892, pl.tx, pl.ty, pl.edge
                )

        if event.key() == Qt.Key_D:
            for i, p in enumerate(self.getcurrentpoly().pointlist):
                pl = self.getcurrentpoly().pointlist[i]
                self.getcurrentpoly().pointlist[i] = mapPoint(
                    pl.x() * 1.1892, pl.y() * 1.1892, pl.tx, pl.ty, pl.edge
                )

        if event.key() == Qt.Key_F:
            self.rotate = True

        if event.key() == Qt.Key_P:
            self.polyproxies.append(PolyProxy())
            self.polyproxies.append(PolyProxy())

        if event.key() == Qt.Key_N:
            self.selected_poly_idx += 1
            self.selected_poly_idx %= len(self.polyproxies)

        self.update()

    #       self.selected_point_idx = None
    #       self.selected_line_idx = None
    #       self.selected_poly_idx = None

    def getcurrentpoly(self):
        return self.polyproxies[self.selected_poly_idx]

    def leftclickevent(self, event):
        self.getcurrentpoly().selected_line_idx = None
        #       self.poly_drag_idx = None
        poly = QPolygonF(self.getcurrentpoly().pointlist)

        for i, point in enumerate(self.getcurrentpoly().pointlist):
            if self.dd(point, event.scenePos()) < 10.0:
                self.getcurrentpoly().point_drag_idx = i
                return

        i = 0

        for p1, p2 in zip(
            self.getcurrentpoly().pointlist[0:-1], self.getcurrentpoly().pointlist[1:]
        ):
            if self.line_intersection(p1, p2, event.scenePos()):
                self.getcurrentpoly().selected_line_idx = i
                return

            i = i + 1

        if poly.containsPoint(event.scenePos(), Qt.OddEvenFill):
            self.poly_drag_idx = self.selected_poly_idx

    def drawBackground(self, painter: QPainter, rect: QRect):
        """Draw background scene grid"""
        super().drawBackground(painter, rect)

        # Here we create our grid
        left = int(math.floor(rect.left()))
        right = int(math.ceil(rect.right()))
        top = int(math.floor(rect.top()))
        bottom = int(math.ceil(rect.bottom()))

        first_left = left - (left % self.gridSize)
        first_top = top - (top % self.gridSize)

        # Compute all lines to be drawn
        lines_light, lines_dark = [], []

        for x in range(first_left, right, self.gridSize):
            if x % (self.gridSize * self.gridSquares) != 0:
                lines_light.append(QLine(x, top, x, bottom))
            else:
                lines_dark.append(QLine(x, top, x, bottom))

        for y in range(first_top, bottom, self.gridSize):
            if y % (self.gridSize * self.gridSquares) != 0:
                lines_light.append(QLine(left, y, right, y))
            else:
                lines_dark.append(QLine(left, y, right, y))

        # Draw the lines
        painter.setPen(self._pen_light)

        try:
            painter.drawLines(*lines_light)  # PyQt5
        except TypeError:
            painter.drawLines(lines_light)  # type: ignore[call-overload] # PySide2

        painter.setPen(self._pen_dark)

        try:
            painter.drawLines(*lines_dark)  # PyQt5
        except TypeError:
            painter.drawLines(lines_dark)  # type: ignore[call-overload] # PySide2

        if DEBUG_STATE:
            try:
                painter.setFont(self._font_state)
                painter.setPen(self._pen_state)
                painter.setRenderHint(QPainter.TextAntialiasing)
                offset = 14
                rect_state = QRect(
                    rect.x() + offset,
                    rect.y() + offset,
                    rect.width() - 2 * offset,
                    rect.height() - 2 * offset,
                )
                painter.drawText(
                    rect_state,
                    Qt.AlignRight | Qt.AlignTop,
                    STATE_STRING[self.views()[0].mode].upper(),
                )
            except Exception:
                dumpException()

        self.drawPolys(painter)
