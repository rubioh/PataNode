import argparse
import gc
import importlib
import os
import sys

from PyQt5.QtWidgets import QApplication

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
        "--fps",
        type=float,
        default=72.0,
        metavar="N",
        help="target frame rate. The render loop paces itself to this cadence "
        "instead of redrawing as fast as it can. 0 means uncapped. With vsync "
        "on, only rates that divide the display's refresh can actually be "
        "held -- on a 144Hz panel that is 144, 72, 48 or 36, so 60 there will "
        "alternate between 13.9ms and 20.8ms frames. Use --vsync off, or a "
        "60Hz output, if you need exactly 60",
    )
    parser.add_argument(
        "--vsync",
        choices=["on", "off"],
        default="on",
        help="sync presentation to the display refresh. With it on, frame "
        "times quantise to multiples of the refresh period; turning it off "
        "lets the pacer alone decide, at the cost of some tearing",
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
    import freeze_log

    # No-op unless PATANODE_FREEZE_LOG is set. After `import app`, because it
    # wraps ShaderWidget.drawFrame to keep its heartbeat.
    freeze_log.install()

    the_app = QApplication(sys.argv)

    # Must follow QApplication: constructing it calls setlocale(LC_ALL, ""),
    # which hands every native library in the process a comma decimal
    # separator on a locale like fr_FR. The Orbbec SDK then misparses its own
    # config and refuses to open the camera. See numeric_locale.
    restoreCNumericLocale()

    the_app.setStyle("Fusion")

    patanode = app.PataShadeApp(args)
    patanode.show()

    # Everything alive at this point is the app's permanent furniture: the
    # imported modules and the shader program registry, which alone is about
    # 154k tracked objects because every node type registers on import.
    #
    # CPython frees almost everything by refcount; the collector exists only
    # to break reference cycles. But a gen-2 pass scans every tracked object
    # in the process and holds the GIL throughout, so at 236k objects it
    # stopped every thread for ~71 ms, roughly once a minute -- a visible
    # hitch in a live set. freeze() moves the current objects into a
    # generation that is never scanned again: measured 71 ms -> 0.8 ms.
    #
    # Before openFile deliberately. Freezing after a scene loads is just as
    # fast, but exempts that scene's objects from cycle collection too, so
    # closing it would leak them. Scenes must stay collectable; the startup
    # furniture never goes away anyway.
    gc.collect()
    gc.freeze()

    if args.open:
        patanode.openFile(args.open)

    the_app.aboutToQuit.connect(freeze_log.report)

    sys.exit(the_app.exec_())
