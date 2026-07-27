"""Wiring checks that do not need a Qt display.

The full app cannot be constructed headlessly, so these assert on the argument
parser and the factory contract rather than on PataShadeApp itself.
"""

import subprocess
import sys

from depth.depth_engine import DepthEngine, DepthStatus
from depth.depth_source import OrbbecSource, SyntheticSource, make_source_factory


def test_main_exposes_a_depth_source_argument():
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )

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
    assert isinstance(make_source_factory("orbbec")(), OrbbecSource)
