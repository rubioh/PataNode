from typing import Literal

from light_new.fixture.fixture import Fixture, FixtureConfigBase
import numpy as np


class CracraConfig(FixtureConfigBase):
    fixture: Literal["cracra"]


class Cracra(Fixture):
    MODEL = "Cracra"
    config: CracraConfig
    CHANNELS_DEFAULTS = {}

    def __init__(self, config: CracraConfig) -> None:
        self.CHANNELS = {
            k: v
            for i in range(8)
            for k, v in {
                f"{i}_dimm": i * 3 + 1,
                f"{i}_strobe": i * 3 + 2,
            }.items()
        }
        self.CHANNELS_DEFAULT = {
            k: v
            for i in range(8)
            for k, v in {
                f"{i}_dimm": 1,
                f"{i}_strobe": 0,
            }.items()
        }

        super().__init__(config)

    def init_params(self):
        self.pixels = np.zeros((8, 2))

    def set_pixels(self, pixels: np.ndarray):
        self.pixels = pixels

    def get_channel_values(self) -> np.ndarray:
        return self.pixels.reshape(-1)
