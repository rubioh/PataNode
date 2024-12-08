import time
import abc

import numpy as np
import usb.core # type: ignore[import-untyped]
import usb.util # type: ignore[import-untyped]

from typing import Callable, Generic, TypeVar, Literal, Annotated, List

from artnet import ArtNetControllerThread, IPv4Address, PortAddr, Universe
from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt, model_validator


DMX_CHANNELS_NUM = 512


class ArtnetOutputConfig(BaseModel):
    output: Literal["artnet"]
    ip: IPv4Address
    port_address_start: NonNegativeInt
    port_address_end: PositiveInt

    @model_validator(mode="after")
    def port_address_validator(self) -> "ArtnetOutputConfig":
        if not self.port_address_end > self.port_address_start:
            raise ValueError(
                "port_address_end must be strictly superior than port_address_start"
            )
        return self


class PataboiteConfig(BaseModel):
    output: Literal["pataboite"]
    universes: PositiveInt


OutputConfig = Annotated[
    ArtnetOutputConfig | PataboiteConfig, Field(discriminator="output")
]


class LightOutputsConfig(BaseModel):
    outputs: list[OutputConfig]


LightOutputConfig = TypeVar("LightOutputConfig")


class LightOutput(abc.ABC, Generic[LightOutputConfig]):
    config: LightOutputConfig

    def __init__(self, config: LightOutputConfig):
        self.config = config

    @property
    @abc.abstractmethod
    def universes(self) -> int: ...

    @abc.abstractmethod
    def write(self, buff: bytes) -> None: ...


class ArtnetOutput(LightOutput[ArtnetOutputConfig]):
    def __init__(
        self,
        config: ArtnetOutputConfig,
        artnet_show: Callable[[bytes, Universe], None],
    ) -> None:
        super().__init__(config)
        self.artnet_show = artnet_show

    @property
    def universes(self) -> int:
        return self.config.port_address_end - self.config.port_address_start

    def write(self, buff: bytes) -> None:
        for i in range(self.universes):
            self.artnet_show(
                buff[DMX_CHANNELS_NUM * i : DMX_CHANNELS_NUM * (i + 1)],
                Universe(self.config.ip, PortAddr(self.config.port_address_start + i)),
            )


class PataboiteOutput(LightOutput[PataboiteConfig]):
    def __init__(self, config) -> None:
        super().__init__(config)
        assert self.config.universes == 1, "pataboite only supports 1 universe for now"
        self.outep: List[usb.core.Endpoint] = []
        self.init_usb_device()

    @property
    def universes(self) -> int:
        return self.config.universes

    def check_usb_devices(self) -> None:
        for device in usb.core.find(find_all=True):
            print(device)

    def init_usb_device(self):
#       self.check_usb_devices()
        self.dev = usb.core.find(idVendor=0x0000, idProduct=0x0001)

        if self.dev is None:
            print("No pataboite gros noob")
        else:
            print("connecting to patalight")
            self.cfg = self.dev.get_active_configuration()
            intf = self.cfg[(0, 0)]

            self.outep.append(
                usb.util.find_descriptor(
                    intf,
                    custom_match=lambda x: usb.util.endpoint_direction(
                        x.bEndpointAddress
                    )
                    == usb.util.ENDPOINT_OUT,
                )
            )

            assert self.outep[0] is not None
            print("connected to patalight")

    def write(self, flat: bytes):
        for idx, outep in enumerate(self.outep):
            outep.write(flat)


class LightOutputs:
    def __init__(self, outputs_conf) -> None:
        artnet_engine = ArtNetControllerThread()
        artnet_engine.start()
        self.artnet_sync = artnet_engine.sync
        config = LightOutputsConfig.model_validate(outputs_conf)
        self.outputs = [
            self.config_to_output(conf, artnet_engine.show) for conf in config.outputs
        ]
        self.universes = sum([out.universes for out in self.outputs])
        print("universes:", self.universes)
        self.prev_ts = time.time()

    @staticmethod
    def config_to_output(
        conf: OutputConfig, artnet_show: Callable[[bytes, Universe], None]
    ) -> LightOutput:
        if isinstance(conf, ArtnetOutputConfig):
            return ArtnetOutput(conf, artnet_show)
        elif isinstance(conf, PataboiteConfig):
            return PataboiteOutput(conf)

    def get_buffer(self) -> np.ndarray:
        return np.zeros((self.universes, DMX_CHANNELS_NUM))

    def write(self, buffer) -> None:
        buffer = np.clip(buffer * 255, 0, 255).astype("u1")
        univ_i = 0

        for output in self.outputs:
            output.write(buffer[univ_i : univ_i + output.universes].tobytes())
            univ_i += output.universes

        self.artnet_sync()
        self.prev_ts = time.time()
