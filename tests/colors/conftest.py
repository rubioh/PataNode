"""Fixtures for colour node tests.

Mirrors tests/session/conftest.py: anything touching a QWidget needs a
live QApplication, and pytest gives each test package its own conftest.

`import program.program_conf` below mirrors tests/depth/conftest.py: any
test module that imports program.colors reaches node.node_conf via
program/colors/__init__.py (which imports the bloom node) before
program.program_conf has finished initialising the registry, producing a
circular-import ImportError. Importing program.program_conf here first
sidesteps it, the same way main.py does.
"""

import pytest
from PyQt5.QtWidgets import QApplication

import program.program_conf  # noqa: F401


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
