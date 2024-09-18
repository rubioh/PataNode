from typing import Literal

from light_new.fixture.fixture import Fixture
from light_new.fixture.mixin import Lyre, RGB, PhysicalPositionFixtureConfig


class Dynamo250Config(PhysicalPositionFixtureConfig):
    fixture: Literal["dynamo250"]


class Dynamo250(Fixture, Lyre):
    # https://jb-systems.eu/fr/dynamo-250
    PAN_LIM = 75
    TILT_LIM = 45
    MODEL = "Dynamo 250"
    config: Dynamo250Config
    CHANNELS = {"pan": 1, "tilt": 2, "shutter": 3, "gobo": 4}
    CHANNELS_DEFAULTS = {
        "pan": 0.5,
        "tilt": 0,
        "shutter": 11 / 255.0,
        "gobo": 120 / 255.0,
    }
