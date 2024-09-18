import abc
import numpy as np
from typing import NamedTuple, Protocol
from light_new.fixture.fixture import FixtureConfigBase


class Fixture(Protocol):
    attrib: dict[str, float]

    def update(self) -> None:
        raise RuntimeError("should inherit from Fixture !")

    def init_params(self) -> None:
        raise RuntimeError("should inherit from Fixture !")


class PhysicalPosition(NamedTuple):
    x: float
    y: float
    z: float

    @property
    def xyz(self) -> np.ndarray:
        return np.array(self)


class PhysicalPositionFixtureConfig(FixtureConfigBase):
    position_3d: PhysicalPosition = PhysicalPosition(0, 0, 0)


class PhysicalPositionFixture(Fixture):
    config: PhysicalPositionFixtureConfig

    @property
    def position_3d(self) -> PhysicalPosition:
        return self.config.position_3d


class Lyre(PhysicalPositionFixture):
    PAN_LIM: int
    TILT_LIM: int
    pan = 0
    tilt = 0

    def pan_tilt_to_dmx(self) -> None:
        if self.pan > self.PAN_LIM:
            self.pan = self.PAN_LIM
        if self.pan < -self.PAN_LIM:
            self.pan = -self.PAN_LIM
        pan = (self.pan + self.PAN_LIM) / (2.0 * self.PAN_LIM)
        self.attrib["pan"] = pan
        if self.tilt > self.TILT_LIM:
            self.tilt = self.TILT_LIM
        if self.tilt < -self.TILT_LIM:
            self.tilt = -self.TILT_LIM
        tilt = (self.tilt + self.TILT_LIM) / (2.0 * self.TILT_LIM)
        self.attrib["tilt"] = tilt

    def lookAt(self, focus_point) -> None:
        pos = self.position_3d.xyz
        target = focus_point
        direction = target - 2.0 * pos
        direction = direction / np.linalg.norm(direction)
        pan = np.arctan2(direction[0], direction[2])
        tilt = -np.arcsin(direction[1]) + np.pi / 2.0
        self.pan = pan / 2.0 / 3.14159 * 360.0
        self.tilt = tilt / 2.0 / 3.14159 * 360.0 - 180.0

    def update(self) -> None:
        self.pan_tilt_to_dmx()
        super().update()


class Color(abc.ABC, Fixture):
    @abc.abstractmethod
    def update_color(self): ...

    def update(self) -> None:
        self.update_color()
        super().update()

    def init_params(self) -> None:
        super().init_params()
        self.color = np.zeros(3)


class CMY(Color):
    def ColorToCMY(self) -> None:
        self.attrib["cyan"] = 1 - self.color[0]
        self.attrib["magenta"] = 1 - self.color[1]
        self.attrib["yellow"] = 1 - self.color[2]

    def update_color(self) -> None:
        self.ColorToCMY()


class RGB(Color):
    def ColorToRGB(self) -> None:
        self.attrib["red"] = self.color[0]
        self.attrib["green"] = self.color[1]
        self.attrib["blue"] = self.color[2]

    def update_color(self) -> None:
        self.ColorToRGB()
