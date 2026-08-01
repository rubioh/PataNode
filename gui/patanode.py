import io
import os
from functools import wraps
from time import time

import numpy as np
from PIL import Image
from PyQt5.QtCore import QEventLoop, QSignalMapper, Qt
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDockWidget,
    QFileDialog,
    QMdiArea,
    QMessageBox,
    QWidget,
)

from gui.graphcontainer import GraphContainerSubWindow
from gui.mappingwindow import PataNodeMappingWindow
from gui.subwindow import PataNodeSubWindow
from gui.widgets.audio_widget import AudioLogWidget
from gui.widgets.drag_listbox_widget import QDMDragListbox
from gui.widgets.inspector_widget import QDMInspector
from gui.widgets.shader_widget import ShaderWidget
from node.node_conf import SHADER_NODES
from nodeeditor.node_editor_window import NodeEditorWindow
from nodeeditor.utils import dumpException, loadStylesheets, pp
from program.map.mapping.mapping import Mapping


def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        print("func:%r args:[%r, %r] took: %2.4f sec" % (f.__name__, args, kw, te - ts))
        return result

    return wrap


DEBUG = False


class PataNode(NodeEditorWindow):
    def __init__(self):
        # Calls initUI
        self.active_graph = None
        self.graphs = {}
        self.previews = {}
        self.next_unique_session_id = 0
        self.queue = []
        super().__init__()

    def initUI(self):
        self.setWindowIcon(QIcon("gui/image/PataNode.png"))

        self.name_company = "PataShade"
        self.name_product = "PataNode"

        self.stylesheet_filename = os.path.join(
            os.path.dirname(__file__), "qss/nodeeditor.qss"
        )

        loadStylesheets(
            os.path.join(os.path.dirname(__file__), "qss/nodeeditor-dark.qss"),
            self.stylesheet_filename,
        )

        self.empty_icon = QIcon(".")

        if DEBUG:
            print("Registered nodes:")
            pp(SHADER_NODES)

        self.mapDisplayed = False
        self.mdiArea = QMdiArea()
        self.mdiArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdiArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdiArea.setViewMode(QMdiArea.TabbedView)
        self.mdiArea.setDocumentMode(True)
        self.mdiArea.setTabsClosable(True)
        self.mdiArea.setTabsMovable(True)
        self.setCentralWidget(self.mdiArea)

        self.mdiArea.subWindowActivated.connect(self.updateMenus)
        self.windowMapper = QSignalMapper(self)
        self.windowMapper.mapped[QWidget].connect(self.setActiveSubWindow)

        # Shader Widget and mgl context initialization
        self.initShaderWidget()
        self.initAudioLogDock()
        self.createNodesDock()
        self.createInspectorDock()

        self.createActions()
        self.createMenus()
        self.createToolBars()
        self.createStatusBar()
        self.updateMenus()

        self.readSettings()

        self.setWindowTitle("PataNode")
        self.initMapWindow()
        self.current_node_editor_widget = None
        self.mapping = Mapping(self.ctx)

    def initMapWindow(self):
        self.mapsubwnd = PataNodeMappingWindow(self)
        self.map_scene = self.mapsubwnd.scene
        self.mapsubwnd.hide()

    def initShaderWidget(self):
        self.gl_widget = ShaderWidget(self)
        self.ctx = self.gl_widget.ctx
        self.waitForShaderWindowExposure()
        self.gl_widget.hide()

    def waitForShaderWindowExposure(self, timeout_s=1.0):
        """Let the shader window finish mapping before it is hidden.

        ShaderWidget.initUI() calls show() so the GL context can be created, and
        the caller hides it again immediately. That races the X server: if the
        hide wins, the window is unmapped before it was ever exposed, and every
        later show()/showFullScreen() then yields a mapped-but-never-exposed
        window. Qt delivers no paint events to an unexposed window, so paintGL
        never runs and the shader output stays blank -- intermittently,
        depending on who wins the race.

        Pumping the event loop until the platform window reports itself exposed
        removes the race. Bounded, so a compositor that never exposes the window
        cannot hang startup.
        """
        deadline = time() + timeout_s

        while time() < deadline:
            handle = self.gl_widget.windowHandle()

            if handle is not None and handle.isExposed():
                return True

            # Waits for events rather than returning immediately, so a window
            # that is never exposed costs an idle second instead of a second
            # of one core at 100%.
            QApplication.processEvents(QEventLoop.AllEvents, 10)

        print("PataNode::initShaderWidget shader window was never exposed")
        return False

    def onHideAudioDock(self, value):
        self.audio_log_widget.setHidden(not value)

    def initAudioLogDock(self):
        self.audio_log_widget = AudioLogWidget(self.audio_engine)
        self.audioDock = QDockWidget("Audio Features")
        self.audioDock.setWidget(self.audio_log_widget)
        self.audioDock.visibilityChanged.connect(self.onHideAudioDock)
        self.audioDock.setFloating(False)
        self.audio_log_widget.resize(1000, 200)
        self.addDockWidget(Qt.TopDockWidgetArea, self.audioDock)
        self.resizeDocks((self.audioDock,), (200,), Qt.Vertical)
        # Hide the audio features when starting the app
        self.audioDock.setVisible(False)

    # Collect infos about graphs and serialize them into json for pataphone

    # @timing
    def poll_graphs(self):
        ret = {"graphs": {}, "graphs_name": []}
        for graph in self.graphs.values():
            counter = {}
            graph_name = str(graph.unique_session_id)
            ret["graphs_name"].append(graph_name)
            ret["graphs"][graph_name] = {
                "is_active": self.active_graph == graph.subwnd,
                "version": graph.version,
                "nodes": {},
                "nodes_name": [],
                "name": graph.getUserFriendlyFilename(),
                "id": graph_name,
            }
            ret["graphs"][graph_name]["has_preview"] = False
            if graph.preview is not None and graph.preview is not False:
                ret["graphs"][graph_name]["has_preview"] = True
            for node in graph.scene.nodes:
                node_name = node.op_title.replace(" ", "")
                if node_name not in counter:
                    counter[node_name] = 0
                else:
                    counter[node_name] = counter[node_name] + 1
                node_name = node_name + str(counter[node_name])
                node.unique_name = node_name
                ret["graphs"][graph_name]["nodes_name"].append(node_name)
                ret["graphs"][graph_name]["nodes"][node_name] = {}
                if node.program:
                    entry = {}
                    params = node.program.getGpuAdaptableParameters()
                    cpu_params = node.program.getCpuAdaptableParameters()
                    bindings = node.program.programs_uniforms.init_binding
                    if "program" not in params:
                        continue
                    # gpu parameters
                    params = params["program"]
                    for param_name, param_values in params.items():
                        param_values = param_values["eval_function"]
                        if (
                            "iChannel" in param_name
                            or "bpm" in param_name
                            or "iTime" in param_name
                        ):
                            continue
                        if param_name == "protected":
                            if param_values:
                                continue
                        value = None
                        if "" in bindings:
                            if param_name in bindings[""]:
                                binding = bindings[""][param_name]["param_name"]
                                if binding:
                                    value = getattr(node.program, binding)

                        entry = {
                            "values": str(param_values["value"]),
                            "type": str(param_values["type"]),
                            "is_default_value": False,
                            "is_cpu_param": False,
                        }
                        if value is not None and "x" in param_values["value"]:
                            entry = {
                                "values": str(value),
                                "type": str(type(value)),
                                "is_default_value": True,
                                "is_cpu_param": False,
                            }
                        if "default_value" not in param_values:
                            param_values["default_value"] = entry["values"]
                            if "x" in entry["values"]:
                                param_values["default_value"] = "x"
                        entry["default_value"] = param_values["default_value"]
                        if "x" not in entry["values"]:
                            ret["graphs"][graph_name]["nodes"][node_name][
                                param_name
                            ] = entry
                    # cpu params
                    for param_name, param_values in cpu_params["program"].items():
                        param_values = param_values
                        value = param_values["eval_function"]["value"]
                        if "default_value" not in param_values:
                            param_values["default_value"] = value
                        default_value = param_values["default_value"]
                        entry = {
                            "default_value": str(default_value),
                            "values": str(value),
                            "type": str(type(value)),
                            "is_cpu_param": True,
                            "is_default_value": value == default_value,
                        }
                        ret["graphs"][graph_name]["nodes"][node_name][
                            param_name
                        ] = entry
        return ret

    def create_bmp_in_memory(self, width, height, bytes):
        img = img = Image.frombytes("RGBA", (width, height), bytes)

        bmp_io = io.BytesIO()
        img.save(bmp_io, format="BMP")
        bmp_data = bmp_io.getvalue()

        return bmp_data

    def set_active_graph(self, id):
        self.queue.append((0, id))

    def update_global_mapping(self, wireframe: bool, polygons: list):
        new_polys = [0] * len(polygons)
        if self.mapping:
            self.mapping.wireframe = wireframe
            for i in range(len(polygons)):
                new_poly = []
                for j in range(len(polygons[i]) // 2):
                    new_poly.append(polygons[i][j * 2])
                    new_poly.append(polygons[i][j * 2 + 1])
                    new_poly.append(self.mapping.base_polygons[0][j * 4 + 2])
                    new_poly.append(self.mapping.base_polygons[0][j * 4 + 3])
                polygons[i] = new_poly
            for i in range(len(polygons) // 2):
                new_polys[i * 2] = polygons[i]
                new_polys[i * 2 + 1] = polygons[i + len(polygons) // 2]
            polygons = new_polys
            self.mapping.updatePolygons(polygons)

    def change_parameter(self, graph_name, node_name, attribute_name, value, is_cpu):
        if graph_name in self.graphs:
            graph = self.graphs[graph_name]
            for node in graph.scene.nodes:
                if not is_cpu:
                    if node.unique_name == node_name:
                        if "program" in node.program.getGpuAdaptableParameters():
                            params = node.program.getGpuAdaptableParameters()["program"]
                            if attribute_name in params:
                                t = type(
                                    params[attribute_name]["eval_function"]["value"]
                                )
                                params[attribute_name]["eval_function"]["value"] = t(
                                    value
                                )
                                return
                else:
                    if node.unique_name == node_name:
                        if "program" in node.program.getCpuAdaptableParameters():
                            params = node.program.getCpuAdaptableParameters()["program"]
                            if attribute_name in params:
                                t = type(
                                    params[attribute_name]["eval_function"]["value"]
                                )
                                params[attribute_name]["eval_function"]["value"] = t(
                                    value
                                )

    def render(self, audio_features=None):
        while len(self.queue) > 0:
            command = self.queue.pop(0)
            id = command[1]
            if command[0] == 0:
                if id in self.graphs.keys():
                    self.setActiveSubWindow(self.graphs[id].subwnd)
                    self.showShaderWindowFromPhone()

        for graph in self.graphs.values():
            graph.mapping = self.mapping
            if graph.should_update_preview():
                graph.render(audio_features, True)
            if graph.preview:
                image = self.create_bmp_in_memory(
                    graph.preview[0][0], graph.preview[0][1], graph.preview[1]
                )
                if graph.unique_session_id not in self.previews:
                    self.previews[str(graph.unique_session_id)] = (graph.version, image)
                elif self.previews[str(graph.unique_session_id)][0] != graph.version:
                    self.previews[str(graph.unique_session_id)] = (graph.version, image)

        # TODO: logic for choosing the rendering program
        if self.current_node_editor_widget is None:
            self.current_node_editor_widget = self.getCurrentNodeEditorWidget()

        if self.current_node_editor_widget is not None:
            self.current_node_editor_widget.render(audio_features)
            self.last_main_colors = self.current_node_editor_widget.getLastMainColors()

        if DEBUG:
            print(
                "PataNode::render  No NodeEditorWidget detected, please set a new node scene"
            )

    def closeEvent(self, event):
        self.mdiArea.closeAllSubWindows()

        if self.mdiArea.currentSubWindow():
            # A subwindow refused to close, so the quit is cancelled and the
            # application must keep running. Nothing may have been torn down
            # before this point.
            event.ignore()
        else:
            self.writeSettings()
            self.releaseAppResources()
            event.accept()
            # Hacky fix for PyQt 5.14.x
            import sys

            sys.exit(0)

    def releaseAppResources(self):
        """Release process-wide resources. Called only once a quit is certain.

        Subclasses override this rather than doing teardown in closeEvent:
        the accept path ends in sys.exit(0), so anything after
        super().closeEvent() never runs, and anything before it also runs on
        the cancelled path -- which would leave a live application with its
        timers stopped and its devices closed.
        """

    def createActions(self):
        super().createActions()

        self.actClose = QAction(
            "Cl&ose",
            self,
            statusTip="Close the active window",
            triggered=self.mdiArea.closeActiveSubWindow,
        )
        self.actCloseAll = QAction(
            "Close &All",
            self,
            statusTip="Close all the windows",
            triggered=self.mdiArea.closeAllSubWindows,
        )
        self.actTile = QAction(
            "&Tile",
            self,
            statusTip="Tile the windows",
            triggered=self.mdiArea.tileSubWindows,
        )
        self.actCascade = QAction(
            "&Cascade",
            self,
            statusTip="Cascade the windows",
            triggered=self.mdiArea.cascadeSubWindows,
        )
        self.actNext = QAction(
            "Ne&xt",
            self,
            shortcut=QKeySequence.NextChild,
            statusTip="Move the focus to the next window",
            triggered=self.mdiArea.activateNextSubWindow,
        )
        self.actPrevious = QAction(
            "Pre&vious",
            self,
            shortcut=QKeySequence.PreviousChild,
            statusTip="Move the focus to the previous window",
            triggered=self.mdiArea.activatePreviousSubWindow,
        )

        self.actMap = QAction(
            "&Map",
            self,
            shortcut="Ctrl+M",
            statusTip="Show mapping window",
            triggered=self.openMapWindow,
        )
        self.actSeparator = QAction(self)
        self.actSeparator.setSeparator(True)

        self.actAbout = QAction(
            "&About",
            self,
            statusTip="Show the application's About box",
            triggered=self.about,
        )

        self.actHideShaderWindow = QAction(
            "&Hide Shader Screen",
            self,
            statusTip="Hide the screen mgl framebuffer",
            triggered=self.hideShaderWindow,
            shortcut="Ctrl+H",
        )
        self.actShowShaderWindow = QAction(
            "&Display Shader Screen",
            self,
            statusTip="Display the screen mgl framebuffer",
            triggered=self.showShaderWindow,
            shortcut="Ctrl+D",
        )

    #       self.actHideAudioLogWindow = QAction("&Hide Audio Log Screen", self, statusTip="Hide the audio features logger", triggered=self.hideShaderWindow, shortcut='Ctrl+Alt+H')
    #       self.actShowAudioLogWindow = QAction("&Display Audio Log Screen", self, statusTip="Display the audio features logger", triggered=self.showShaderWindow, shortcut='Ctrl+Alt+D')

    def hideShaderWindow(self):
        self.gl_widget.hide()

    def showShaderWindowFromPhone(self):
        self.current_node_editor_widget = None
        self.active_graph = self.mdiArea.activeSubWindow()
        self.gl_widget.showFullScreen()

    def showShaderWindow(self):
        self.current_node_editor_widget = None
        for k in self.graphs:
            self.graphs[k].version = self.graphs[k].version + 1
        self.active_graph = self.mdiArea.activeSubWindow()
        self.gl_widget.showFullScreen()

    def hideAudioLogWindow(self):
        self.audio_log_widget.setVisible(False)

    def showAudioLogWindow(self):
        self.audio_log_widget.setVisible(True)

    def getCurrentNodeEditorWidget(self):
        """we're returning NodeEditorWidget here..."""
        activeSubWindow = self.mdiArea.activeSubWindow()

        if activeSubWindow:
            return activeSubWindow.widget()

        return None

    def openMapWindow(self):
        if self.mapDisplayed:
            self.mapsubwnd.hide()
        else:
            self.mapsubwnd.showMaximized()

        self.mapDisplayed = not self.mapDisplayed

    def onFileNew(self):
        try:
            subwnd = self.createMdiChild()
            subwnd.widget().fileNew()
            subwnd.show()
        except Exception as e:
            dumpException(e)

    def onFileOpen(self, graph=False):
        fnames, filter = QFileDialog.getOpenFileNames(
            self,
            "Open graph from file",
            self.getFileDialogDirectory(),
            self.getFileDialogFilter(),
        )

        try:
            for fname in fnames:
                if fname:
                    nodeeditor, subwnd = self.openFile(fname, graph)
        except Exception as e:
            dumpException(e)

        if graph:
            return nodeeditor, subwnd

    def openFile(self, filename, graph=False):
        existing = self.findMdiChild(filename)
        if existing:
            self.setActiveSubWindow(existing)
        else:
            # We need to create a new subWindow and open the file
            if graph:
                nodeeditor = GraphContainerSubWindow(self)
            else:
                nodeeditor = PataNodeSubWindow(self)

            if nodeeditor.fileLoad(filename):
                self.statusBar().showMessage("File %s loaded" % filename, 5000)
                nodeeditor.setTitle()
                subwnd = self.createMdiChild(nodeeditor)
                subwnd.show()

                if graph:
                    nodeeditor.initGraphScene()
            else:
                nodeeditor.close()

        return nodeeditor, subwnd

    def about(self):
        QMessageBox.about(self, "About PataNode", "Un logiciel de bg pour les bgs")

    def createMenus(self):
        super().createMenus()

        self.windowMenu = self.menuBar().addMenu("&Window")
        self.updateWindowMenu()
        self.windowMenu.aboutToShow.connect(self.updateWindowMenu)

        self.menuBar().addSeparator()

        self.helpMenu = self.menuBar().addMenu("&Help")
        self.helpMenu.addAction(self.actAbout)

        self.mapMenu = self.menuBar().addMenu("&Map")
        self.mapMenu.addAction(self.actMap)

        self.editMenu.aboutToShow.connect(self.updateEditMenu)

    def updateMenus(self):
        active = self.getCurrentNodeEditorWidget()
        hasMdiChild = active is not None

        self.actSave.setEnabled(hasMdiChild)
        self.actSaveAs.setEnabled(hasMdiChild)
        self.actClose.setEnabled(hasMdiChild)
        self.actCloseAll.setEnabled(hasMdiChild)
        self.actTile.setEnabled(hasMdiChild)
        self.actCascade.setEnabled(hasMdiChild)
        self.actNext.setEnabled(hasMdiChild)
        self.actPrevious.setEnabled(hasMdiChild)
        self.actSeparator.setVisible(hasMdiChild)

        self.updateEditMenu()

    def updateEditMenu(self):
        try:
            active = self.getCurrentNodeEditorWidget()
            hasMdiChild = active is not None

            self.actPaste.setEnabled(hasMdiChild)

            self.actCut.setEnabled(hasMdiChild and active.hasSelectedItems())
            self.actCopy.setEnabled(hasMdiChild and active.hasSelectedItems())
            self.actDelete.setEnabled(hasMdiChild and active.hasSelectedItems())

            self.actUndo.setEnabled(hasMdiChild and active.canUndo())
            self.actRedo.setEnabled(hasMdiChild and active.canRedo())
        except Exception as e:
            dumpException(e)

    def updateWindowMenu(self):
        self.windowMenu.clear()

        toolbar_nodes = self.windowMenu.addAction("Nodes Toolbar")
        toolbar_nodes.setCheckable(True)
        toolbar_nodes.triggered.connect(self.onWindowNodesToolbar)
        toolbar_nodes.setChecked(self.nodesDock.isVisible())

        self.windowMenu.addSeparator()
        self.windowMenu.addAction(self.actClose)
        self.windowMenu.addAction(self.actCloseAll)
        self.windowMenu.addSeparator()
        self.windowMenu.addAction(self.actTile)
        self.windowMenu.addAction(self.actCascade)
        self.windowMenu.addSeparator()
        self.windowMenu.addAction(self.actNext)
        self.windowMenu.addAction(self.actPrevious)
        self.windowMenu.addAction(self.actSeparator)
        self.windowMenu.addSeparator()
        self.windowMenu.addAction(self.actHideShaderWindow)
        self.windowMenu.addAction(self.actShowShaderWindow)
        #       self.windowMenu.addAction(self.actHideAudioLogWindow)
        #       self.windowMenu.addAction(self.actShowAudioLogWindow)

        windows = self.mdiArea.subWindowList()
        self.actSeparator.setVisible(len(windows) != 0)

        for i, window in enumerate(windows):
            child = window.widget()

            text = "%d %s" % (i + 1, child.getUserFriendlyFilename())

            if i < 9:
                text = "&" + text

            action = self.windowMenu.addAction(text)
            action.setCheckable(True)
            action.setChecked(child is self.getCurrentNodeEditorWidget())
            action.triggered.connect(self.windowMapper.map)
            self.windowMapper.setMapping(action, window)

    def onWindowNodesToolbar(self):
        if self.nodesDock.isVisible():
            self.nodesDock.hide()
        else:
            self.nodesDock.show()

    def createToolBars(self):
        pass

    def createNodesDock(self):
        self.nodesListWidget = QDMDragListbox()

        self.nodesDock = QDockWidget("Nodes")
        self.nodesDock.setWidget(self.nodesListWidget)
        self.nodesDock.setFloating(False)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.nodesDock)
        self.resizeDocks((self.nodesDock,), (220,), Qt.Horizontal)

    def createInspectorDock(self):
        self.inspector_widget = QDMInspector()
        self.inspectorDock = QDockWidget("Inspector")
        self.inspectorDock.setWidget(self.inspector_widget)
        self.inspectorDock.setFloating(False)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspectorDock)
        self.resizeDocks((self.inspectorDock,), (300,), Qt.Horizontal)

    def updateInspector(self, obj):
        if obj.__class__ in SHADER_NODES.values():
            self.inspector_widget.updateParametersToSelectedItems(obj)

    def createStatusBar(self):
        self.statusBar().showMessage("Ready")

    def createMdiChild(self, child_widget=None):
        nodeeditor = (
            child_widget if child_widget is not None else PataNodeSubWindow(self)
        )
        if nodeeditor.__class__ == PataNodeSubWindow:
            nodeeditor.set_unique_session_id(self.next_unique_session_id)
            self.next_unique_session_id = self.next_unique_session_id + 1
        subwnd = self.mdiArea.addSubWindow(nodeeditor)
        subwnd.setWindowIcon(self.empty_icon)
        #       nodeeditor.scene.addItemSelectedListener(self.updateEditMenu)
        #       nodeeditor.scene.addItemsDeselectedListener(self.updateEditMenu)
        nodeeditor.scene.history.addHistoryModifiedListener(self.updateEditMenu)
        nodeeditor.addCloseEventListener(self.onSubWndClose)
        nodeeditor.subwnd = subwnd
        self.graphs[str(nodeeditor.unique_session_id)] = nodeeditor
        return subwnd

    def releaseNodeResources(self, widget):
        # Closing a graph subwindow does not clear its scene or call
        # node.remove() -- neither closeEvent nor onSubWndClose ever did, and
        # WA_DeleteOnClose is disabled on PataNodeSubWindow. Nodes that hold
        # external resources beyond the scene (the depth camera's acquire()
        # refcount is the current example) would otherwise stay held for the
        # rest of the session, or leak further on every repeated open/close
        # of the same file. This is a narrow, targeted release -- NOT a
        # scene.clear() -- so it must never raise out of closeEvent: guard
        # every attribute access and isolate each node's failure from the
        # rest.
        scene = getattr(widget, "scene", None)
        nodes = getattr(scene, "nodes", None)
        if not nodes:
            return

        for node in list(nodes):
            remove = getattr(node, "remove", None)
            if remove is None:
                continue
            try:
                remove()
            except Exception as e:
                dumpException(e)

    def onSubWndClose(self, widget, event):
        existing = self.findMdiChild(widget.filename)
        self.graphs = {k: v for k, v in self.graphs.items() if not v.mark_dead}
        self.mdiArea.setActiveSubWindow(existing)

        if self.maybeSave():
            # Only release once the close is actually going through: doing
            # this before the gate would tear down the graph (detach every
            # edge, drop every grNode, empty scene.nodes) of a window the
            # user just chose to keep open by cancelling the save prompt.
            self.releaseNodeResources(widget)
            event.accept()
        else:
            event.ignore()

    def findMdiChild(self, filename):
        for window in self.mdiArea.subWindowList():
            if window.widget().filename == filename:
                return window

        return None

    def setActiveSubWindow(self, window):
        if window:
            self.mdiArea.setActiveSubWindow(window)

    def getFileDialogFilter(self):
        return "Graph (*.json *.pn);;All files (*)"

    def getFileDialogDirectory(self):
        """Returns starting directory for ``QFileDialog`` file open/save"""
        return "saved"
