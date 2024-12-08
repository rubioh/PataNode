from typing import Literal

from light_new.fixture.fixture import Fixture
from light_new.fixture.mixin import Lyre, PhysicalPositionFixtureConfig, RGB


class Mac301Config(PhysicalPositionFixtureConfig):
    fixture: Literal["mac301"]


class Mac301(Lyre, RGB, Fixture):
    PAN_LIM = 215
    TILT_LIM = 150
    MODEL = "Mac 301"
    config: Mac301Config
    CHANNELS = {
        "pan": 1,
        "pan_fine": 2,
        "tilt": 3,
        "tilt_fine": 4,
        "general_control": 5,
        "shutter": 6,
        "dimmer": 7,
        "zoom": 8,
        "red": 9,
        "green": 10,
        "blue": 11,
        "wheel": 12,
        "pan_tilt_speed": 13,
        "effects_speed": 14,
        "movement_blackout": 15,
    }
    CHANNELS_DEFAULTS = {"shutter": 0.1, "dimmer": 1}
