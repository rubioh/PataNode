import numpy as np

from typing import Literal, NamedTuple

from pydantic import Field, PositiveInt, NonNegativeInt

from light_new.fixture.fixture import Fixture, FixtureConfigBase


class Position3D(NamedTuple):
    x: float
    y: float
    z: float


class LightStringConfig(FixtureConfigBase):
    fixture: Literal["light_string"]
    length: PositiveInt

    # Special value of 0 means it has a neon aspect
    px_per_section: NonNegativeInt = Field(default=1)

    position_start: Position3D = Field(default=[0, 0, 0])
    position_end: Position3D = Field(default=[0, 0, 0])


class LightString(Fixture):
    MODEL = "Light String"
    config: LightStringConfig
    CHANNELS_DEFAULTS = {}

    def __init__(self, config: LightStringConfig) -> None:
        self.CHANNELS = {
            k: v
            for i in range(config.length)
            for k, v in {
                f"{i}_red": i * 3 + 1,
                f"{i}_green": i * 3 + 2,
                f"{i}_blue": i * 3 + 3,
            }.items()
        }

        super().__init__(config)

    def init_params(self):
        self.pixels = np.zeros((self.config.length, 3))

    def set_pixels(self, pixels: np.ndarray):
        assert pixels.shape == (self.config.length, 3)
        self.pixels = pixels

    def get_channel_values(self) -> np.ndarray:
        return self.pixels.reshape(-1)
