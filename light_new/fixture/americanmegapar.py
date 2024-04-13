from typing import Literal

from light_new.fixture.fixture import Fixture, FixtureConfigBase
from light_new.fixture.mixin import RGB


class AmericanMegaParConfig(FixtureConfigBase):
    fixture: Literal["americanmegapar"]


class AmericanMegaPar(Fixture, RGB):
    # https://www.fullcompass.com/common/files/14961-AmericanDJMegaParProfileUserManual.pdf
    MODEL = "American Mega Par"
    config: AmericanMegaParConfig
    CHANNELS = {
        "red": 1,
        "green": 2,
        "blue": 3,
        "dimmer": 4,
    }
    CHANNELS_DEFAULTS = {
        "dimmer": 1,
    }
