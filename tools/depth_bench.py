"""Measure the render loop's frame cadence with the depth camera running.

Committed rather than thrown away so the before and after arms run byte-identical
measurement code. The metric that matters is the tail, not the mean: GIL
contention from the depth thread leaves p50 untouched and wrecks p99.

    PATASHADE_INPUT_DEVICE=9 .venv/bin/python tools/depth_bench.py \
        --label before --seconds 60 --out baseline.json
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import QTimer  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

import program.program_conf  # noqa: F401,E402
from numeric_locale import restoreCNumericLocale  # noqa: E402

SESSION = "saved/laignes.pnlive"


def build_scene(path):
    """Write the session's last state out as a plain scene file."""
    import json as _json

    with open(SESSION) as handle:
        live = _json.load(handle)

    with open(path, "w") as handle:
        _json.dump(live["states"][-1]["scene"], handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fps", type=float, default=72.0)
    parser.add_argument("--depth-source", default="orbbec")
    args = parser.parse_args()

    scene = "/tmp/depth_bench_scene.pn"
    build_scene(scene)

    the_app = QApplication(sys.argv[:1])
    restoreCNumericLocale()
    the_app.setStyle("Fusion")

    import app as app_module
    from gui.widgets.shader_widget import ShaderWidget

    stamps = []
    original = ShaderWidget.drawFrame

    def timed(self):
        # Only count a cycle as a presented frame if it completed without
        # raising. renderFrame() wraps drawFrame() in its own try/finally so
        # the render loop survives an exception; that behavior is preserved
        # here by letting the exception propagate unchanged, we just don't
        # record a timestamp for it.
        result = original(self)
        stamps.append(time.perf_counter())
        return result

    ShaderWidget.drawFrame = timed

    app_args = argparse.Namespace(
        open=scene,
        debug=None,
        no_usb=None,
        use_shader_buffer=None,
        server=False,
        fps=args.fps,
        vsync="on",
        depth_source=args.depth_source,
    )

    patanode = app_module.PataShadeApp(app_args)
    patanode.show()
    patanode.openFile(scene)
    patanode.showShaderWindow()

    def report():
        # Drop the first 40 frames: startup, shader compilation and the
        # camera's first frames are not what this measures.
        warm = stamps[40:]
        intervals = sorted((b - a) * 1000 for a, b in zip(warm, warm[1:]))
        n = len(intervals)
        span = warm[-1] - warm[0]

        result = {
            "label": args.label,
            "seconds": args.seconds,
            "depth_source": args.depth_source,
            "frames": len(warm),
            "fps": (len(warm) - 1) / span,
            "p50": intervals[n // 2],
            "p95": intervals[int(n * 0.95)],
            "p99": intervals[int(n * 0.99)],
            "max": intervals[-1],
            "over_30ms": sum(1 for x in intervals if x > 30),
            "over_50ms": sum(1 for x in intervals if x > 50),
            "over_100ms": sum(1 for x in intervals if x > 100),
        }

        with open(args.out, "w") as handle:
            json.dump(result, handle, indent=2)

        print(json.dumps(result, indent=2))
        the_app.quit()

    QTimer.singleShot(int(args.seconds * 1000), report)
    the_app.exec_()


if __name__ == "__main__":
    main()
