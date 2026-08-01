"""Initialise the program registry before any test imports a program module.

`program/input/__init__.py` imports the depth input module, which reaches
node.node_conf, which reaches program.program_conf, which imports the whole
program package -- so importing a program module directly hits a partially
initialised node.node_conf. main.py sidesteps this by importing
program.program_conf first; conftest is the equivalent hook for tests, and
being in conftest keeps the ordering safe from isort.
"""

import program.program_conf  # noqa: F401
