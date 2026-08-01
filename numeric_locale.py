"""Keep the C numeric locale neutral for native libraries.

Qt calls setlocale(LC_ALL, "") when QApplication is constructed, adopting the
user's locale. Under a comma-decimal locale (fr_FR, de_DE, ...) every C or C++
library in the process that parses numbers with strtod/atof starts reading "1.0"
as 1, because the separator it expects is now a comma.

The Orbbec SDK does exactly that when it parses its frame-processor config, so
the depth camera fails to open with:

    Filter@FrameProcessor: config item DisparityTransform#2 value 1 out of range [0, 0]

which reads like a hardware fault and is not one.

Deliberately dependency-free so it can be imported from the entry point before
anything else, and tested without dragging in the application graph.
"""

import locale


def restoreCNumericLocale():
    """Pin LC_NUMERIC to "C", leaving every other category as the user set it.

    Only LC_NUMERIC is dangerous. Resetting LC_ALL would also revert collation
    and date formatting, which the user chose on purpose and which Qt renders
    correctly. Python's own float parsing is locale-independent, so this costs
    the application nothing.
    """
    locale.setlocale(locale.LC_NUMERIC, "C")
