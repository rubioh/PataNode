"""The Inspector asks whether a node offers a preview -- it never learns
which node that is. Any future node inherits the toggle by declaring
preview_window_class.
"""

from PyQt5.QtWidgets import QCheckBox, QWidget

from gui.widgets.inspector_widget import QDMInspector


class DummyWindow(QWidget):
    def __init__(self, node):
        super().__init__()


class FakeNode:
    preview_window_class = None

    def __init__(self):
        self.visible = False

    def setPreviewWindowVisible(self, visible):
        self.visible = visible

    def isPreviewWindowVisible(self):
        return self.visible


class PreviewNode(FakeNode):
    preview_window_class = DummyWindow


def checkboxes(widget):
    return widget.findChildren(QCheckBox)


def test_a_node_without_a_preview_gets_no_toggle(qapp):
    inspector = QDMInspector()
    assert inspector.createPreviewToggle(FakeNode()) is None


def test_a_node_with_a_preview_gets_one_toggle(qapp):
    inspector = QDMInspector()
    box = inspector.createPreviewToggle(PreviewNode())
    assert box is not None
    assert len(checkboxes(box)) == 1


def test_ticking_the_toggle_opens_the_preview(qapp):
    inspector = QDMInspector()
    node = PreviewNode()
    box = inspector.createPreviewToggle(node)

    checkboxes(box)[0].setChecked(True)

    assert node.visible is True


def test_unticking_the_toggle_hides_the_preview(qapp):
    inspector = QDMInspector()
    node = PreviewNode()
    node.visible = True
    box = inspector.createPreviewToggle(node)

    checkboxes(box)[0].setChecked(True)
    checkboxes(box)[0].setChecked(False)

    assert node.visible is False


def test_the_toggle_reflects_a_window_already_open(qapp):
    """Re-selecting a node whose preview is open must not show an unticked
    box beside a visible window."""
    inspector = QDMInspector()
    node = PreviewNode()
    node.visible = True

    box = inspector.createPreviewToggle(node)

    assert checkboxes(box)[0].isChecked() is True


class InspectableNode(FakeNode):
    """Enough of a node for the real updateParametersToSelectedItems: the
    panel builder also asks for a resolution button and three toolboxes."""

    win_size = (1920, 1080)

    def changeWindowSize(self, win_size):
        self.win_size = win_size

    def getUniformsBinding(self):
        return {}

    def getGpuAdaptableParameters(self):
        return {}

    def getCpuAdaptableParameters(self):
        return {}


class InspectablePreviewNode(InspectableNode):
    preview_window_class = DummyWindow


def panelCheckboxes(inspector):
    """The checkboxes the built panel actually contains.

    Not inspector.findChildren: clearLayout only calls deleteLater, so the
    previous panel's widgets survive until the event loop runs.
    """
    found = []
    for index in range(inspector.grid.count()):
        widget = inspector.grid.itemAt(index).widget()

        if widget is not None:
            found += widget.findChildren(QCheckBox)

    return found


def test_the_panel_builder_adds_the_toggle(qapp):
    """createPreviewToggle can be perfect and still never be called -- or
    called and its result dropped. Runs the real builder and looks for the
    checkbox in the panel it produced."""
    inspector = QDMInspector()

    inspector.updateParametersToSelectedItems(InspectablePreviewNode())

    labels = [box.text() for box in panelCheckboxes(inspector)]
    assert labels.count("Palette preview") == 1


def test_the_panel_builder_omits_the_toggle_for_a_plain_node(qapp):
    inspector = QDMInspector()

    inspector.updateParametersToSelectedItems(InspectableNode())

    labels = [box.text() for box in panelCheckboxes(inspector)]
    assert "Palette preview" not in labels


def test_the_toggle_in_the_built_panel_opens_the_preview(qapp):
    """The checkbox that reaches the panel is a live one, not a copy."""
    inspector = QDMInspector()
    node = InspectablePreviewNode()

    inspector.updateParametersToSelectedItems(node)
    box = [b for b in panelCheckboxes(inspector) if b.text() == "Palette preview"][0]
    box.setChecked(True)

    assert node.visible is True
