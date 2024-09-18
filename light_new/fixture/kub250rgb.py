from typing import Literal

from light_new.fixture.fixture import Fixture
from light_new.fixture.mixin import Lyre, RGB, PhysicalPositionFixtureConfig


class Kub250RGBConfig(PhysicalPositionFixtureConfig):
    fixture: Literal["kub250"]


class Kub250RGB(Fixture):
    # https://static.boomtonedj.com/pdf/manual/48/48144_manualkub250rgbfren.pdf
    PAN_LIM = 75
    TILT_LIM = 45
    MODEL = "BoomTone Kub 250 RGB"
    config: Kub250RGBConfig
    CHANNELS = {
        "mode": 1,
        "pattern_selection": 2,
        "pattern_rotation": 3,
        "pattern_horizontal_rotation": 4,
        "pattern_vertical_rotation": 5,
        "pattern_horizontal_movement": 6,
        "pattern_vertical_movement": 7,
        "zoom_pattern": 8,
        "color_selection": 9,
        "effect": 10,
    }
    CHANNELS_DEFAULTS = {
        "mode": 90 / 255.0,
        "pattern_selection": 0,
        "pattern_rotation": 0,
        "pattern_horizontal_rotation": 0,
        "pattern_vertical_rotation": 0,
        "pattern_horizontal_movement": 0,
        "pattern_vertical_movement": 0,
        "zoom_pattern": 65 / 255.0,
        "color_selection": 0,
    }
