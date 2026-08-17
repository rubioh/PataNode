"""Fixtures for render-loop and uniform-binding tests.

`import program.program_conf` mirrors tests/colors/conftest.py and
tests/depth/conftest.py: importing program.program_base directly reaches
node.node_conf through the package __init__ chain before
program.program_conf has finished initialising the registry, which raises a
circular-import ImportError. Importing program.program_conf first sidesteps
it, the same way main.py does.
"""

import program.program_conf  # noqa: F401
