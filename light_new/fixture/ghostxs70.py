from typing import Literal

from light_new.fixture.fixture import Fixture
from light_new.fixture.mixin import Lyre, RGB, PhysicalPositionFixtureConfig


class GhostXS70Config(PhysicalPositionFixtureConfig):
    fixture: Literal["ghostxs70"]


class GhostXS70(Fixture, Lyre, RGB):
    # http://mlkweb.free.fr/_fields/Lyre%20Ghost%20XS70.pdf
    PAN_LIM = 180  # 360-540
    TILT_LIM = 90  # 180
    MODEL = "Ghost XS 70"
    config: GhostXS70Config
    CHANNELS = {
        "pan": 1,
        "tilt": 2,
        "dimmer": 3,  # 0-9 close || 10-134 dimmer || 135-239 strobe || 240-255 open
        "red": 4,
        "green": 5,
        "blue": 6,
        "white": 7,
        "speed": 8,
    }
    CHANNELS_DEFAULTS = {"pan": 0.5, "tilt": 0.5, "dimmer": 55.0 / 255.0, "speed": 1.0}
