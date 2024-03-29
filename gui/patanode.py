import os
import time

from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import QMdiArea, QWidget, QDockWidget, QAction, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt, QSignalMapper

from nodeeditor.utils import loadStylesheets
from nodeeditor.node_editor_window import NodeEditorWindow
from nodeeditor.utils import dumpException, pp

from gui.subwindow import PataNodeSubWindow
from gui.widgets.drag_listbox_widget import QDMDragListbox
from gui.widgets.shader_widget import ShaderWidget
from gui.widgets.inspector_widget import QDMInspector
from gui.widgets.audio_widget import AudioLogWidget

from node.node_conf import SHADER_NODES



DEBUG = False


class PataNode(NodeEditorWindow):

    def __init__(self, audio_engine=None):
        self.audio_engine = audio_engine
        super().__init__()

    def initUI(self):
        self.name_company = 'PataShade'
        self.name_product = 'PataNode'

        self.stylesheet_filename = os.path.join(os.path.dirname(__file__), "qss/nodeeditor.qss")
        loadStylesheets(
            os.path.join(os.path.dirname(__file__), "qss/nodeeditor-dark.qss"),
            self.stylesheet_filename
        )

        self.empty_icon = QIcon(".")

        if DEBUG:
            print("Registered nodes:")
            pp(SHADER_NODES)


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


        # Shader Widget and mgl context Initialization
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

        self.current_program = None

    def initShaderWidget(self):
        self.gl_widget = ShaderWidget(self, self.audio_engine)
        self.ctx = self.gl_widget.ctx
        self.gl_widget.hide()

    def onHideAudioDock(self, value):
        self.audio_log_widget.setHidden(not value)

    def initAudioLogDock(self):
        self.audio_log_widget = AudioLogWidget(self.audio_engine)
        self.audioDock = QDockWidget("Audio Features")
        self.audioDock.setWidget(self.audio_log_widget)
        self.audioDock.visibilityChanged.connect(self.onHideAudioDock)
        self.audioDock.setFloating(False)
        self.audio_log_widget.resize(1000,200)
        self.addDockWidget(Qt.TopDockWidgetArea, self.audioDock)
        self.resizeDocks((self.audioDock,), (200,), Qt.Vertical)
        # Hide the audio features on starting the app
        self.audioDock.setVisible(False)


    def render(self, audio_features=None):
        # TODO logic for choosing the rendering program
        if self.current_program is None:
            self.current_program = self.getCurrentNodeEditorWidget()
        if self.current_program is not None:
            self.current_program.render(audio_features)
        if DEBUG: print('PataNode::render  No NodeEditorWidget detected, please set a new node scene')

    def closeEvent(self, event):
        self.mdiArea.closeAllSubWindows()
        if self.mdiArea.currentSubWindow():
            event.ignore()
        else:
            self.writeSettings()
            event.accept()
            # hacky fix for PyQt 5.14.x
            import sys
            sys.exit(0)


    def createActions(self):
        super().createActions()

        self.actClose = QAction("Cl&ose", self, statusTip="Close the active window", triggered=self.mdiArea.closeActiveSubWindow)
        self.actCloseAll = QAction("Close &All", self, statusTip="Close all the windows", triggered=self.mdiArea.closeAllSubWindows)
        self.actTile = QAction("&Tile", self, statusTip="Tile the windows", triggered=self.mdiArea.tileSubWindows)
        self.actCascade = QAction("&Cascade", self, statusTip="Cascade the windows", triggered=self.mdiArea.cascadeSubWindows)
        self.actNext = QAction("Ne&xt", self, shortcut=QKeySequence.NextChild, statusTip="Move the focus to the next window", triggered=self.mdiArea.activateNextSubWindow)
        self.actPrevious = QAction("Pre&vious", self, shortcut=QKeySequence.PreviousChild, statusTip="Move the focus to the previous window", triggered=self.mdiArea.activatePreviousSubWindow)

        self.actSeparator = QAction(self)
        self.actSeparator.setSeparator(True)

        self.actAbout = QAction("&About", self, statusTip="Show the application's About box", triggered=self.about)

        self.actHideShaderWindow = QAction("&Hide Shader Screen", self, statusTip="Hide the screen mgl framebuffer", triggered=self.hideShaderWindow, shortcut='Ctrl+H')
        self.actShowShaderWindow = QAction("&Display Shader Screen", self, statusTip="Display the screen mgl framebuffer", triggered=self.showShaderWindow, shortcut='Ctrl+D')
        #self.actHideAudioLogWindow = QAction("&Hide Audio Log Screen", self, statusTip="Hide the audio features logger", triggered=self.hideShaderWindow, shortcut='Ctrl+Alt+H')
        #self.actShowAudioLogWindow = QAction("&Display Audio Log Screen", self, statusTip="Display the audio features logger", triggered=self.showShaderWindow, shortcut='Ctrl+Alt+D')

    def hideShaderWindow(self):
        self.gl_widget.hide()

    def showShaderWindow(self):
        self.gl_widget.show()

    def hideAudioLogWindow(self):
        self.audio_log_widget.setVisible(False)

    def showAudioLogWindow(self):
        self.audio_log_widget.setVisible(True)

    def getCurrentNodeEditorWidget(self):
        """ we're returning NodeEditorWidget here... """
        activeSubWindow = self.mdiArea.activeSubWindow()
        if activeSubWindow:
            return activeSubWindow.widget()
        return None

    def onFileNew(self):
        try:
            subwnd = self.createMdiChild()
            subwnd.widget().fileNew()
            subwnd.show()
        except Exception as e: dumpException(e)


    def onFileOpen(self):
        fnames, filter = QFileDialog.getOpenFileNames(self, 'Open graph from file', self.getFileDialogDirectory(), self.getFileDialogFilter())

        try:
            for fname in fnames:
                if fname:
                    existing = self.findMdiChild(fname)
                    if existing:
                        self.mdiArea.setActiveSubWindow(existing)
                    else:
                        # we need to create new subWindow and open the file
                        nodeeditor = PataNodeSubWindow(self)
                        if nodeeditor.fileLoad(fname):
                            self.statusBar().showMessage("File %s loaded" % fname, 5000)
                            nodeeditor.setTitle()
                            subwnd = self.createMdiChild(nodeeditor)
                            subwnd.show()
                        else:
                            nodeeditor.close()
        except Exception as e: dumpException(e)


    def about(self):
        QMessageBox.about(self, "About PataNode NodeEditor Example",
                "The <b>PataNode NodeEditor</b> example demonstrates how to write multiple "
                "document interface applications using PyQt5 and NodeEditor. For more information visit: "
                "<a href='https://www.blenderfreak.com/'>www.BlenderFreak.com</a>")

    def createMenus(self):
        super().createMenus()

        self.windowMenu = self.menuBar().addMenu("&Window")
        self.updateWindowMenu()
        self.windowMenu.aboutToShow.connect(self.updateWindowMenu)

        self.menuBar().addSeparator()

        self.helpMenu = self.menuBar().addMenu("&Help")
        self.helpMenu.addAction(self.actAbout)

        self.editMenu.aboutToShow.connect(self.updateEditMenu)


    def updateMenus(self):
        # print("update Menus")
        active = self.getCurrentNodeEditorWidget()
        hasMdiChild = (active is not None)

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
            # print("update Edit Menu")
            active = self.getCurrentNodeEditorWidget()
            hasMdiChild = (active is not None)

            self.actPaste.setEnabled(hasMdiChild)

            self.actCut.setEnabled(hasMdiChild and active.hasSelectedItems())
            self.actCopy.setEnabled(hasMdiChild and active.hasSelectedItems())
            self.actDelete.setEnabled(hasMdiChild and active.hasSelectedItems())

            self.actUndo.setEnabled(hasMdiChild and active.canUndo())
            self.actRedo.setEnabled(hasMdiChild and active.canRedo())
        except Exception as e: dumpException(e)



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
        #self.windowMenu.addAction(self.actHideAudioLogWindow)
        #self.windowMenu.addAction(self.actShowAudioLogWindow)

        windows = self.mdiArea.subWindowList()
        self.actSeparator.setVisible(len(windows) != 0)

        for i, window in enumerate(windows):
            child = window.widget()

            text = "%d %s" % (i + 1, child.getUserFriendlyFilename())
            if i < 9:
                text = '&' + text

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
        self.inspector_widget.updateParametersToSelectedItems(obj)

    def createStatusBar(self):
        self.statusBar().showMessage("Ready")

    def createMdiChild(self, child_widget=None):
        nodeeditor = child_widget if child_widget is not None else PataNodeSubWindow(self)
        subwnd = self.mdiArea.addSubWindow(nodeeditor)
        subwnd.setWindowIcon(self.empty_icon)
        # nodeeditor.scene.addItemSelectedListener(self.updateEditMenu)
        # nodeeditor.scene.addItemsDeselectedListener(self.updateEditMenu)
        nodeeditor.scene.history.addHistoryModifiedListener(self.updateEditMenu)
        nodeeditor.addCloseEventListener(self.onSubWndClose)
        return subwnd

    def onSubWndClose(self, widget, event):
        existing = self.findMdiChild(widget.filename)
        self.mdiArea.setActiveSubWindow(existing)

        if self.maybeSave():
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

