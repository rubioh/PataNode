import abc
import numpy as np


class Color:
    def __init__(self):
        self.color = np.zeros(3)

    def update_color(self): ...

    def update(self, color: list | None = None) -> None:
        if color is not None:
            self.color[:] = color
        self.update_color()


class CMY(Color):
    def ColorToCMY(self) -> None:
        self.attrib["cyan"] = 1 - self.color[0]
        self.attrib["magenta"] = 1 - self.color[1]
        self.attrib["yellow"] = 1 - self.color[2]

    def update_color(self) -> None:
        self.ColorToCMY()


class RGB(Color):
    def ColorToRGB(self) -> None:
        self.attrib["red"] = self.color[0]
        self.attrib["green"] = self.color[1]
        self.attrib["blue"] = self.color[2]

    def update_color(self) -> None:
        self.ColorToRGB()
