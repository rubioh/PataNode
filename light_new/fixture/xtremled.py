from typing import Literal

from light_new.fixture.fixture import Fixture
from light_new.fixture.mixin import Lyre, RGB, PhysicalPositionFixtureConfig


class XtremLedConfig(PhysicalPositionFixtureConfig):
    fixture: Literal["xtremled"]


class XtremLed(Fixture):
    # https://static.boomtonedj.com/pdf/manual/44/44625_xtremledmanual.pdf
    MODEL = "Xtrem Led BoomTone DJ"
    config: XtremLedConfig
    CHANNELS = {
        "custom": 1,
        "moon_flower": 2,
        "colors": 3,  # 7colors between 1 and 202
        "strobe": 4,
        "motor": 5,
        "strobe_speed": 6,
    }
    CHANNELS_DEFAULTS = {
        "custom": 0,
        "moon_flower": 1 / 255.0,
        "colors": 1.0 / 255.0,
        "strobe": 0,
        "strobe_speed": 0,
    }
