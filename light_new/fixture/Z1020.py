from typing import Literal

from light_new.fixture.fixture import Fixture, FixtureConfigBase


class Z1020Config(FixtureConfigBase):
    fixture: Literal["antari_z1020"]


class Z1020(Fixture):
    MODEL = "Z1020"
    config: Z1020Config
    CHANNELS = {"enable": 1}
    CHANNELS_DEFAULTS = {"enable": 0}
