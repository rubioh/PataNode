from typing import Literal

from light_new.fixture.fixture import Fixture, FixtureConfigBase


class Par2BrodConfig(FixtureConfigBase):
    fixture: Literal["par2brod"]


class Par2Brod(Fixture):
    MODEL = "par2brod"
    config: Par2BrodConfig
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
    }
