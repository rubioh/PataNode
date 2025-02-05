from typing import Literal

from light.fixture.fixture import Fixture
from light.fixture.mixin import RGB
from light.fixture.config import register_light, name_to_opcode

OP_CODE_CLASSICPAR = name_to_opcode("ClassicPar")

@register_light(OP_CODE_CLASSICPAR)
class ClassicPar(Fixture, RGB):
    MODEL = "ClassicPar"
    CHANNELS = {
        "red": 1,
        "green": 2,
        "blue": 3,
        "white": 4,
        "amber": 5,
        "uv": 6,
        "dimmer": 7,
        "strobe": 8,
    }
    CHANNELS_DEFAULTS = {
        "dimmer": 1,
        "strobe": 1
    }
    def __init__(self, args):
        super().__init__(args)
        super(RGB, self).__init__()

    def update(self, color: list|None = None):
        super(RGB, self).update(color)
