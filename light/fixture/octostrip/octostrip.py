import numpy as np

from typing import Literal

from light.fixture.fixture import Fixture
from light.fixture.mixin import RGB
from light.fixture.config import register_light, name_to_opcode

OP_CODE_OCTOSTRIP = name_to_opcode("OCTOSTRIP")

@register_light(OP_CODE_OCTOSTRIP)
class Octostrip(Fixture):
    MODEL = "Octostrip"
    CHANNELS = {}
    for j in range(8):
        CHANNELS.update({
            f"strob_{j}": 2 + 2*j,
            f"dim_{j}": 1 + 2*j
        })
        for i in range(8):
            CHANNELS.update({
                f"red_{i}_{j}": 17+3*i+24*j,
                f"green_{i}_{j}": 18+3*i+24*j,
                f"blue_{i}_{j}": 19+3*i+24*j
            })
    CHANNELS_DEFAULTS = {
        "dim_0": 1,
        "dim_1": 1,
        "dim_2": 1,
        "dim_3": 1,
        "dim_4": 1,
        "dim_5": 1,
        "dim_6": 1,
        "dim_7": 1,
        f"blue_0_0": 1,
        f"blue_1_0": 1,
        f"blue_2_0": 1,
        f"blue_3_0": 1,
        f"red_0_1": 1,
        f"red_1_1": 1,
        f"red_2_1": 1,
        f"red_3_1": 1,
        f"green_0_2": 1,
        f"green_1_2": 1,
        f"green_2_2": 1,
        f"green_3_2": 1,
    }
    def __init__(self, args):
        super().__init__(args)
        self.build_canvas_position()

    def build_canvas_position(self):
        x_s = self.canvas_position[0][0]
        x_f = self.canvas_position[1][0]
        y_s = self.canvas_position[0][1]
        y_f = self.canvas_position[1][1]
        res = np.meshgrid(np.linspace(x_s, x_f, 8), np.linspace(y_s, y_f, 8))
        positions = list()
        for X in np.linspace(x_s, x_f, 8):
            for Y in np.linspace(y_s, y_f, 8):
                positions.append([int(X), int(Y)])
        self.canvas_position = positions

    def get_sub_light(self, idx):
        sub_light_attrib = {}

    def update(self, colors: list|None = None):
        for j in range(8):
            for i in range(8):
                self.attrib[f"red_{i}_{j}"] = colors[j*8 + i, 0]
                self.attrib[f"green_{i}_{j}"] = colors[j*8 + i, 1]
                self.attrib[f"blue_{i}_{j}"] = colors[j*8 + i, 2]
