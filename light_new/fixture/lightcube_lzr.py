from typing import Literal

from light_new.fixture.fixture import Fixture
from light_new.fixture.mixin import RGB, PhysicalPositionFixtureConfig


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
    CHANNELS_DEFAULTS = {
        "dimmer": 0.5,
        "strobe": 0.0,
        "red": 0.5,
        "green": 0.5,
        "blue": 0.5,
        "white": 0.0,
        "laser": 0.0,
        "rotation": 0.5,
        "auto_rotation": 0.0,
    }
