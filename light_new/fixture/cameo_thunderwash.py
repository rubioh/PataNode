from typing import Literal

from light_new.fixture.fixture import Fixture
from light_new.fixture.mixin import Lyre, RGB, PhysicalPositionFixtureConfig


class CameoThunderWashConfig(PhysicalPositionFixtureConfig):
    fixture: Literal["cameothunderwash"]


class CameoThunderWash(RGB, Fixture):
    # https://www.nordsoundsystems.fr/wp-content/uploads/2020/02/CAMEO_Thunderwash_600_RGBW_Manuel_FR-1.pdf
    MODEL = "Cameo Thunder Wash"
    config: CameoThunderWashConfig
    CHANNELS = {
        "dimmer": 1,
        "strobe": 2,
        "red": 3,
        "green": 4,
        "blue": 5,
        "white": 6,
        "sound": 7,
    }
    CHANNELS_DEFAULTS = {"dimmer": .1, "strobe":.0, "red":.5, "green":.0, "blue":.0, "white":.0, "sound":0.}
