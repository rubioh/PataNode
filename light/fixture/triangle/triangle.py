from typing import Literal

from light.fixture.fixture import Fixture
from light.fixture.mixin import RGB
from light.fixture.config import register_light, name_to_opcode

OP_CODE_TRIANGLE = name_to_opcode("Triangle")


@register_light(OP_CODE_TRIANGLE)
class Triangle(Fixture, RGB):
    MODEL = "Triangle"
    CHANNELS = {"red": 1, "green": 2, "blue": 3}
    CHANNELS_DEFAULTS = {}

    def __init__(self, args):
        super().__init__(args)
        super(RGB, self).__init__()

    def update(self, color: list | None = None):
        super(RGB, self).update(color)
