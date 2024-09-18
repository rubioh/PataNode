import numpy as np
from typing import TypeVar, Generic, NamedTuple
import abc
from pydantic import BaseModel, PositiveInt


class FixtureAddress(NamedTuple):
    universe: PositiveInt
    dmx_start_channel: PositiveInt


class FixtureConfigBase(BaseModel):
    name: str
    address: FixtureAddress


FixtureConfigVar = TypeVar("FixtureConfigVar", bound=FixtureConfigBase)


class Fixture(abc.ABC, Generic[FixtureConfigVar]):
    MODEL: str
    config: FixtureConfigVar
    CHANNELS: dict[str, int]
    CHANNELS_DEFAULTS: dict[str, float]
    attrib: dict[str, float]

    def __init__(self, config: FixtureConfigVar) -> None:
        self.config = config
        self.init_params()

    def update(self) -> None: ...

    def get_channel_values(self) -> np.ndarray:
        buffer_length = len(self.CHANNELS)
        fixture_buffer = np.zeros(buffer_length)
        for c, idx in self.CHANNELS.items():
            fixture_buffer[idx - 1] = self.attrib[c]
        return fixture_buffer

    def init_params(self) -> None:
        self.attrib = {k: 0.0 for k in self.CHANNELS.keys()}
        for k, v in self.CHANNELS_DEFAULTS.items():
            self.attrib[k] = v

    def __str__(self):
        return f"Name : {self.MODEL} with id {self.config.name}\n \t\tUniverse : {self.config.address.universe}, Address : {self.config.address.dmx_start_channel} \n"
