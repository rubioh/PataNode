from typing import Literal

from light_new.fixture.fixture import Fixture
from light_new.fixture.mixin import Lyre, CMY, PhysicalPositionFixtureConfig


class AlphaspotConfig(PhysicalPositionFixtureConfig):
    fixture: Literal["alphaspot"]


class Alphaspot(Lyre, CMY, Fixture):
    PAN_LIM = 270
    TILT_LIM = 125
    MODEL = "AlphaSpot 300"
    config: AlphaspotConfig
    CHANNELS = {
        "cyan": 1,
        "magenta": 2,
        "yellow": 3,
        "uniform_field_lens": 4,
        "colour_wheel": 5,
        "strobe": 6,
        "dimmer": 7,
        "iris": 8,
        "fixed_gobo_change": 9,
        "rotating_gobo_change": 10,
        "gobo_rotation": 11,
        "gobo_fine": 12,
        "prism_insertion": 13,
        "prism_rotation": 14,
        "frost": 15,
        "focus": 16,
        "zoom": 17,
        "pan": 18,
        "pan_fine": 19,
        "tilt": 20,
        "tilt_fine": 21,
        "reset": 22,
        "lamp_on_off": 23,
    }
    CHANNELS_DEFAULTS = {"lamp_on_off": 0.95}
