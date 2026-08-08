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


def test_the_panel_builder_adds_the_toggle(qapp, monkeypatch):
    """createPreviewToggle can be perfect and still never be called."""
    inspector = QDMInspector()
    calls = []
    monkeypatch.setattr(inspector, "createSetWinSizeToolbox", lambda obj: None)
    monkeypatch.setattr(inspector, "createGpuParametersToolbox", lambda info: None)
    monkeypatch.setattr(inspector, "createCpuParametersToolbox", lambda info: None)
    monkeypatch.setattr(inspector, "createUniformsToolbox", lambda binding: None)
    monkeypatch.setattr(
        inspector,
        "createPreviewToggle",
        lambda node: calls.append(node) or None,
    )

    class Obj:
        def getUniformsBinding(self):
            return {}

        def getGpuAdaptableParameters(self):
            return {}

        def getCpuAdaptableParameters(self):
            return {}

    obj = Obj()
    inspector.updateParametersToSelectedItems(obj)

    assert calls == [obj]
