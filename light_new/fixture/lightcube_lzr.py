from typing import Literal

from light_new.fixture.fixture import Fixture
from light_new.fixture.mixin import Lyre, RGB, PhysicalPositionFixtureConfig


class LightCubeLZRConfig(PhysicalPositionFixtureConfig):
    fixture: Literal["lightcubelzr"]


class LightCubeLZR(RGB, Fixture):
    PAN_LIM = 215
    TILT_LIM = 150
    MODEL = "Light Cube LZR"
    config: LightCubeLZRConfig
    CHANNELS = {
        "dimmer": 1,
        "strobe": 2,
        "red": 3,
        "green": 4,
        "blue": 5,
        "white": 6,
        "laser": 7,
        "rotation": 8,
        "auto_rotation": 9,
    }
    CHANNELS_DEFAULTS = {"dimmer": .5, "strobe":.0, "red":.5, "green":.5, "blue":.5, "white":.0, "laser":0., "rotation": .5, "auto_rotation":.0}
