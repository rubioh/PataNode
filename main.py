import argparse
import importlib
import os
import sys

import program.program_conf  # noqa: F401
from numeric_locale import restoreCNumericLocale

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="PataNode", description="The node-oriented shader manager"
    )
    parser.add_argument("-o", "--open", metavar="filename")
    parser.add_argument("--debug", metavar="module_to_debug", nargs="+")
    parser.add_argument("--no-usb", metavar="no_usb")
    parser.add_argument("--use-shader-buffer", metavar="use_shader_buffer")
    parser.add_argument("--server", action="store_true")
    parser.add_argument(
        "--profile",
        nargs="?",
        type=int,
        const=120,
        default=0,
        metavar="FRAMES",
        help="print a per-node CPU/GPU timing table every FRAMES frames "
        "(default 120, about 2s at 60fps)",
    )
    parser.add_argument(
        "--paint-loop",
        choices=["timer", "event"],
        default="timer",
        help="how the render loop asks for its next frame. 'timer' posts an "
        "ordinary timer event; 'event' calls update(), which on a QGLWidget "
        "becomes a native WM_PAINT -- the lowest-priority message Windows has",
    )
    parser.add_argument(
        "--vsync",
        choices=["on", "off"],
        default="on",
        help="sync presentation to the display refresh. With it on, frame "
        "times quantise to multiples of the refresh period; turning it off "
        "shows what the loop can actually produce",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=60.0,
        metavar="N",
        help="target frame rate. The loop paces itself to this cadence "
        "instead of redrawing as fast as it can. 0 means uncapped",
    )
    parser.add_argument(
        "--frame-interval",
        type=int,
        default=0,
        metavar="MS",
        help="interval of the render loop's re-arm timer. 0 makes it a Qt "
        "zero-timer, which stops the event dispatcher from ever blocking and "
        "makes it spin through every pending event between frames; 1 or 2 "
        "gives a real timer that lets the loop idle",
    )
    parser.add_argument(
        "--profile-no-gpu",
        action="store_true",
        help="profile without GL timer queries. Drops the gpu ms column, and "
        "tells you whether the queries themselves were perturbing the frame",
    )
    parser.add_argument(
        "--profile-events",
        action="store_true",
        help="also account every Qt event delivered on the GUI thread, by "
        "receiver and type. Finds work no targeted span was looking for",
    )
    parser.add_argument(
        "--depth-source",
        choices=["orbbec", "synthetic"],
        default="orbbec",
        help="depth camera backend; 'synthetic' fakes a camera for development",
    )
    args = parser.parse_args()

    if args.debug:
        for module_to_debug in args.debug:
            if os.path.exists(module_to_debug):
                module_to_debug = module_to_debug.replace(os.sep, ".")[:-3]

            print(f"[debug] debugging {module_to_debug}")
            importlib.import_module(module_to_debug).DEBUG = True

    # Note: This import is here to avoid a circular import
    import app
    import profiler

    # Must be the QApplication actually used: notify() is only overridable on
    # the instance that ends up dispatching events.
    the_app = profiler.make_application(sys.argv, args.profile_events)

    # Must follow QApplication: constructing it calls setlocale(LC_ALL, ""),
    # which hands every native library in the process a comma decimal
    # separator on a locale like fr_FR. The Orbbec SDK then misparses its own
    # config and refuses to open the camera. See numeric_locale.
    restoreCNumericLocale()

    the_app.setStyle("Fusion")

    patanode = app.PataShadeApp(args)
    patanode.show()

    if args.open:
        patanode.openFile(args.open)

    sys.exit(the_app.exec_())
