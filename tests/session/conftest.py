"""Fixtures for session tests.

Plain nodeeditor Node/Edge need no GL context, but Scene builds a
QDMGraphicsScene, which needs a live QApplication.
"""

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def scene(qapp):
    from nodeeditor.node_node import Node
    from nodeeditor.node_scene import Scene

    built = Scene()
    # Every node in these tests is a plain Node; the union model only needs
    # a class, and plain Node ignores restore_window_size via **kwargs.
    built.setNodeClassSelector(lambda data: Node)
    return built
