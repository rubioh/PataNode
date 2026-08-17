"""Wiring checks that do not need a Qt display.

The full app cannot be constructed headlessly, so these assert on the argument
parser and the factory contract rather than on PataShadeApp itself.
"""

import os
import subprocess
import sys

from depth.depth_engine import DepthEngine, DepthStatus
from depth.depth_process import ProcessSource
from depth.depth_source import SyntheticSource, make_source_factory

# Anchored on this file's location, not the process cwd: pytest may be invoked
# from anywhere, and a cwd-relative "main.py" would either raise or (worse)
# silently resolve to an unrelated file if some other main.py were on the cwd.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN_PATH = os.path.join(REPO_ROOT, "main.py")


def test_main_exposes_a_depth_source_argument():
    result = subprocess.run(
        [sys.executable, MAIN_PATH, "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=REPO_ROOT,
    )

    # Assert the process actually succeeded before trusting stdout: otherwise
    # an import failure in main.py surfaces as a confusing "--depth-source
    # not in stdout" rather than the real error.
    assert result.returncode == 0, result.stderr

    assert "--depth-source" in result.stdout
    assert "synthetic" in result.stdout


def test_an_engine_built_from_the_default_factory_stays_idle():
    # Constructing the engine must not open the camera; nothing should happen
    # until a node acquires it.
    engine = DepthEngine(make_source_factory("orbbec"))

    assert engine.status is DepthStatus.IDLE
    assert engine.get_frame() is None


def test_the_synthetic_factory_is_selected_by_name():
    assert isinstance(make_source_factory("synthetic")(), SyntheticSource)
    assert isinstance(make_source_factory("orbbec")(), ProcessSource)
