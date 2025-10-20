from typing import Literal

import numpy as np

from light.fixture.fixture import Fixture
from light.fixture.mixin import RGB
from light.fixture.config import register_light, name_to_opcode

OP_CODE_RUBAN_LED = name_to_opcode("RubanLed")

@register_light(OP_CODE_RUBAN_LED)
class RubanLed(Fixture):
    MODEL = "RubanLed"
    CHANNELS_DEFAULTS = {}
    CHANNELS = {}
    def __init__(self, args):
        super().__init__(args)
        self.colors = np.zeros(self.num_pixels*3)
        print("INIT")

    def update(self, color: list|None = None):
        self.colors = color.reshape(-1)

    def get_dmx_buffer(self):
        return self.colors
