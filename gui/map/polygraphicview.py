# -*- coding: utf-8 -*-
"""
A module containing `Graphics View` for NodeEditor
"""

from qtpy.QtCore import Signal, QPoint, Qt
from qtpy.QtGui import QPainter
from qtpy.QtWidgets import QGraphicsView

from nodeeditor.node_edge_dragging import EdgeDragging
from nodeeditor.node_edge_intersect import EdgeIntersect
from nodeeditor.node_edge_rerouting import EdgeRerouting
from nodeeditor.node_edge_snapping import EdgeSnapping
from nodeeditor.node_graphics_cutline import QDMCutLine


MODE_NOOP = 1  #: Mode representing ready state
MODE_EDGE_DRAG = 2  #: Mode representing when we drag edge state
MODE_EDGE_CUT = 3  #: Mode representing when we draw a cutting edge
MODE_EDGES_REROUTING = 4  #: Mode representing when we re-route existing edges
MODE_NODE_DRAG = 5  #: Mode representing when we drag a node to calculate dropping on intersecting edge

STATE_STRING = ["", "Noop", "Edge Drag", "Edge Cut", "Edge Rerouting", "Node Drag"]

#: Distance when click on socket to enable `Drag Edge`
EDGE_DRAG_START_THRESHOLD = 50

#: Enable UnrealEngine style rerouting
EDGE_REROUTING_UE = True

#: Socket snapping distance
EDGE_SNAPPING_RADIUS = 24
#: Enable socket snapping feature
EDGE_SNAPPING = True

DEBUG = False
DEBUG_MMB_SCENE_ITEMS = False
DEBUG_MMB_LAST_SELECTIONS = False
DEBUG_EDGE_INTERSECT = False
DEBUG_STATE = False


class PolyGraphicView(QGraphicsView):
    """Class representing NodeEditor's `Graphics View`"""

    #: pyqtSignal emitted when cursor position on the `Scene` has changed
    scenePosChanged = Signal(int, int)

    def __init__(self, grScene: "QDMGraphicsScene", parent: "QWidget" = None):
        """
        :param grScene: reference to the :class:`~nodeeditor.node_graphics_scene.QDMGraphicsScene`
        :type grScene: :class:`~nodeeditor.node_graphics_scene.QDMGraphicsScene`
        :param parent: parent widget
        :type parent: ``QWidget``

        :Instance Attributes:

        - **grScene** - reference to the :class:`~nodeeditor.node_graphics_scene.QDMGraphicsScene`
        - **mode** - state of the `Graphics View`
        - **zoomInFactor**- ``float`` - zoom step scaling, default 1.25
        - **zoomClamp** - ``bool`` - do we clamp zooming or is it infinite?
        - **zoom** - current zoom step
        - **zoomStep** - ``int`` - the relative zoom step when zooming in/out
        - **zoomRange** - ``[min, max]``

        """
        super().__init__(parent)
        self.grScene = grScene

        self.initUI()

        self.setScene(self.grScene)

        self.mode = MODE_NOOP
        self.editingFlag = False
        self.rubberBandDraggingRectangle = False

        # edge dragging
        self.dragging = EdgeDragging(self)

        # edges re-routing
        self.rerouting = EdgeRerouting(self)

        # drop a node on an existing edge
        self.edgeIntersect = EdgeIntersect(self)

        # edge snapping
        self.snapping = EdgeSnapping(self, snapping_radius=EDGE_SNAPPING_RADIUS)

        # cutline
        self.cutline = QDMCutLine()
        self.grScene.addItem(self.cutline)

        self.last_scene_mouse_position = QPoint(0, 0)
        self.zoomInFactor = 1.25
        self.zoomClamp = True
        self.zoom = 10
        self.zoomStep = 1
        self.zoomRange = [0, 10]

        # listeners
        self._drag_enter_listeners = []
        self._drop_listeners = []

    def initUI(self):
        """Set up this ``QGraphicsView``"""
        self.setRenderHints(
            QPainter.Antialiasing
            | QPainter.HighQualityAntialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )

        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)

        # enable dropping
        self.setAcceptDrops(True)
