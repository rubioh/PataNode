"""Palette evaluation and the floating preview window for Value Gradient."""

import colorsys
import math

TWO_PI = 2.0 * math.pi


def palette_rgb(t, frequency, phases, saturation):
    """Cosine palette, mirroring value_gradient.glsl exactly.

    `t` is the input value and is clamped to [0, 1] here for the same
    reason the shader clamps it: the FBOs are f4 float targets, so an
    upstream node can deliver out-of-range channels, and `t` is used
    twice -- once to index the palette, once as the output brightness.

    The palette supplies hue and saturation only; `t` comes back as
    brightness so the input's relief survives colourisation.
    """
    t = min(1.0, max(0.0, t))
    palette = [
        0.5 + 0.5 * math.cos(TWO_PI * (frequency * t + phase)) for phase in phases
    ]
    hue, sat, _ = colorsys.rgb_to_hsv(*palette)
    return colorsys.hsv_to_rgb(hue, sat * saturation, t)


from PyQt5.QtCore import QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QLinearGradient, QPainter
from PyQt5.QtWidgets import QWidget

PARAM_NAMES = ("frequency", "phase_r", "phase_g", "phase_b", "saturation")
GRADIENT_STOPS = 32
REFRESH_MS = 50


class PalettePreviewWindow(QWidget):
    """Free-floating live preview of one Value Gradient node's palette.

    Refreshed by a timer rather than a signal: the parameters move from two
    directions -- Inspector edits and per-frame audio modulation -- and only
    the second would be practical to hook. Polling catches both, and
    evaluating a cosine 32 times at 20 Hz costs nothing beside the 60 Hz
    render already running.
    """

    def __init__(self, node):
        super().__init__()
        self.node = node
        self.setWindowTitle("Palette — %s" % getattr(node, "title", "Value Gradient"))
        self.resize(360, 150)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(REFRESH_MS)

    def currentParams(self):
        """The values the shader actually received, falling back to the
        program attributes before the node has ever rendered."""
        program = self.node.program
        last_values = program.programs_uniforms.last_values.get("", {})

        values = []
        for name in PARAM_NAMES:
            if name in last_values:
                values.append(float(last_values[name]))
            else:
                values.append(float(getattr(program, name)))

        frequency, phase_r, phase_g, phase_b, saturation = values
        return frequency, (phase_r, phase_g, phase_b), saturation

    def paintEvent(self, event):
        frequency, phases, saturation = self.currentParams()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        band = QRectF(12, 12, self.width() - 24, self.height() - 74)
        gradient = QLinearGradient(band.topLeft(), band.topRight())
        for step in range(GRADIENT_STOPS + 1):
            t = step / GRADIENT_STOPS
            r, g, b = palette_rgb(t, frequency, phases, saturation)
            gradient.setColorAt(t, QColor(int(r * 255), int(g * 255), int(b * 255)))
        painter.fillRect(band, gradient)

        painter.setPen(QColor(200, 200, 200))
        text = "frequency %.3f\nphase  %.3f  %.3f  %.3f\nsaturation %.3f" % (
            frequency,
            phases[0],
            phases[1],
            phases[2],
            saturation,
        )
        painter.drawText(
            QRectF(12, band.bottom() + 8, self.width() - 24, 60),
            Qt.AlignLeft | Qt.AlignTop,
            text,
        )
        painter.end()

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
