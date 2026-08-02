"""Fixtures for the scene save/load tests.

These exercise the plain nodeeditor `Scene`/`Node`/`Edge` types, so no GL
context is needed -- but `Scene` builds a `QDMGraphicsScene`, which needs a
live QApplication.
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
    from nodeeditor.node_scene import Scene

    return Scene()


@pytest.fixture
def two_node_scene(scene):
    """A minimal scene: two nodes joined by one edge."""
    from nodeeditor.node_edge import Edge
    from nodeeditor.node_node import Node

    node_a = Node(scene, "Node A", inputs=[1], outputs=[1])
    node_b = Node(scene, "Node B", inputs=[1], outputs=[1])
    Edge(scene, node_a.outputs[0], node_b.inputs[0])
    return scene
