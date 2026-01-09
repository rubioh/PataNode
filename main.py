import argparse
import importlib
import os
import sys

from PyQt5.QtWidgets import QApplication

import program.program_conf  # noqa: F401

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="PataNode", description="The node-oriented shader manager"
    )
    parser.add_argument("-o", "--open", metavar="filename")
    parser.add_argument("--debug", metavar="module_to_debug", nargs="+")
    parser.add_argument("--no-usb", metavar="no_usb")
    parser.add_argument("--use-shader-buffer", metavar="use_shader_buffer")
    parser.add_argument("--server", action="store_true")
    args = parser.parse_args()

    if args.debug:
        for module_to_debug in args.debug:
            if os.path.exists(module_to_debug):
                module_to_debug = module_to_debug.replace(os.sep, ".")[:-3]

            print(f"[debug] debugging {module_to_debug}")
            importlib.import_module(module_to_debug).DEBUG = True

    # Note: This import is here to avoid a circular import
    import app

    the_app = QApplication(sys.argv)
    the_app.setStyle("Fusion")

    patanode = app.PataShadeApp(args)
    patanode.show()

    if args.open:
        patanode.openFile(args.open)

    sys.exit(the_app.exec_())
