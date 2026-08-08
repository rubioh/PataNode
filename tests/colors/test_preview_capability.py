"""The preview window is owned by the node, not the Inspector.

Selecting another node runs QDMInspector.clearLayout (inspector_widget.py:199),
which deletes the whole panel -- an Inspector-owned window would be orphaned
on every selection change, and several previews could not stay open at once.
"""

from PyQt5.QtWidgets import QWidget

from node.shader_node_base import ShaderNode


class DummyWindow(QWidget):
    def __init__(self, node):
        super().__init__()
        self.node = node


class PreviewNode(ShaderNode):
    """A ShaderNode with the capability but without ShaderNode.__init__,
    which builds a GL program and needs a live context."""

    preview_window_class = DummyWindow

    def __init__(self):
        self._preview_window = None


class PlainNode(ShaderNode):
    def __init__(self):
        self._preview_window = None


def test_a_node_without_the_capability_opens_nothing(qapp):
    node = PlainNode()
    node.setPreviewWindowVisible(True)
    assert node.isPreviewWindowVisible() is False


def test_showing_creates_the_window(qapp):
    node = PreviewNode()
    node.setPreviewWindowVisible(True)
    assert node.isPreviewWindowVisible() is True


def test_the_window_is_created_once_and_reused(qapp):
    """Re-opening must not leave a trail of orphaned windows behind."""
    node = PreviewNode()
    node.setPreviewWindowVisible(True)
    first = node._preview_window
    node.setPreviewWindowVisible(False)
    node.setPreviewWindowVisible(True)
    assert node._preview_window is first


def test_hiding_does_not_destroy_the_window(qapp):
    node = PreviewNode()
    node.setPreviewWindowVisible(True)
    node.setPreviewWindowVisible(False)
    assert node._preview_window is not None
    assert node.isPreviewWindowVisible() is False


def test_removing_the_node_closes_its_window(qapp, monkeypatch):
    """Otherwise the window outlives its node, with a timer polling a
    program that no longer exists."""
    from nodeeditor.node_node import Node

    monkeypatch.setattr(Node, "remove", lambda self: None)

    node = PreviewNode()
    node.setPreviewWindowVisible(True)
    window = node._preview_window

    node.remove()

    assert window.isVisible() is False
    assert node._preview_window is None
