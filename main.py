import argparse
import sys

from PyQt5.QtWidgets import QApplication

# Note: This import is here to avoid a circular import
import program.program_conf # noqa: F401

from app import PataShade

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="PataNode", description="The node-oriented shader manager")
    parser.add_argument("-o", "--open", metavar="filename")

    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    patanode = PataShade()
    patanode.show()

    if args.open:
        patanode.openFile(args.open)

    sys.exit(app.exec_())
