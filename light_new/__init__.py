import yaml
from light_new.light_outputs import LightOutputs
from light_new.fixture import (
    Fixture,
    Mac301Config,
    AlphaspotConfig,
    Mac301,
    Alphaspot,
    LightString,
    LightStringConfig,
    Z1020,
    Z1020Config,
    Par2Brod,
    Par2BrodConfig,
    LightCubeLZR,
    LightCubeLZRConfig,
    CameoThunderWash,
    CameoThunderWashConfig,
    Dynamo250,
    Dynamo250Config,
    GhostXS70,
    GhostXS70Config,
    Kub400RGB,
    Kub400RGBConfig,
    Kub250RGB,
    Kub250RGBConfig,
    XtremLed,
    XtremLedConfig,
    AmericanMegaPar,
    AmericanMegaParConfig,
)
from light_new.cracra import Cracra, CracraConfig
from light_new.patterns import PatternManager
from typing import Annotated
from pydantic import Field, BaseModel
import time

FixtureConfig = Annotated[
    Z1020Config
    | CracraConfig
    | Mac301Config
    | AlphaspotConfig
    | LightStringConfig
    | Par2BrodConfig
    | LightCubeLZRConfig
    | CameoThunderWashConfig
    | Dynamo250Config
    | GhostXS70Config
    | Kub400RGBConfig
    | Kub250RGBConfig
    | XtremLedConfig
    | AmericanMegaParConfig,
    Field(discriminator="fixture"),
]


class FixturesConfig(BaseModel):
    fixtures: list[FixtureConfig]


class InvalidConfigurationError(Exception): ...


class LightEngine:
    def __init__(self):
        DEFAULT_SCENO_PATH = "light_new/current_sceno.yml"
        try:
            self.sceno = yaml.load(open(DEFAULT_SCENO_PATH), Loader=yaml.CLoader)
        except FileNotFoundError:
            print(f"Unable to open sceno file `{DEFAULT_SCENO_PATH}`")
            print(
                "hint: you may need to create a new sceno file: `cp -i light/example.json light/current-sceno.json`"
            )
            exit(1)

        self.outputs = LightOutputs(self.sceno)
        self.init_fixtures(self.sceno)
        for f in self.fixtures:
            print(f.config)
        self.pattern_manager = PatternManager()
        self.last_kick_count = self.last_hat_count = self.last_snare_count = 0

    def init_fixtures(self, fixtures_conf) -> None:
        config = FixturesConfig.model_validate(fixtures_conf)
        fixtures = [self.config_to_fixture(conf) for conf in config.fixtures]
        names = list[str]()
        for i, f in enumerate(fixtures):
            if f.config.name in names:
                raise InvalidConfigurationError(
                    f"duplicate name for fixture {i}: `{f.config.name}'"
                )
            names += [f.config.name]
        self.fixtures = fixtures

    def config_to_fixture(self, conf: FixtureConfig) -> Fixture:
        if isinstance(conf, AlphaspotConfig):
            return Alphaspot(conf)
        elif isinstance(conf, Z1020Config):
            return Z1020(conf)
        elif isinstance(conf, CracraConfig):
            return Cracra(conf)
        elif isinstance(conf, Mac301Config):
            return Mac301(conf)
        elif isinstance(conf, LightStringConfig):
            return LightString(conf)
        elif isinstance(conf, Par2BrodConfig):
            return Par2Brod(conf)
        elif isinstance(conf, LightCubeLZRConfig):
            return LightCubeLZR(conf)
        elif isinstance(conf, CameoThunderWashConfig):
            return CameoThunderWash(conf)
        elif isinstance(conf, Dynamo250Config):
            return Dynamo250(conf)
        elif isinstance(conf, GhostXS70Config):
            return GhostXS70(conf)
        elif isinstance(conf, Kub400RGBConfig):
            return Kub400RGB(conf)
        elif isinstance(conf, Kub250RGBConfig):
            return Kub250RGB(conf)
        elif isinstance(conf, XtremLedConfig):
            return XtremLed(conf)
        elif isinstance(conf, AmericanMegaParConfig):
            return AmericanMegaPar(conf)

    def exit(self):
        buffer = [0] * 512
        self.outputs.write(buffer)
        self.pattern_manager.exit()

    def set_audio_features(self, audio_features):
        self.af = audio_features
        self.af["on_kick"] = 1 if self.last_kick_count != self.af["kick_count"] else 0
        self.af["on_hat"] = 1 if self.last_hat_count != self.af["hat_count"] else 0
        self.af["on_snare"] = (
            1 if self.last_snare_count != self.af["snare_count"] else 0
        )
        self.last_kick_count = self.af["kick_count"]
        self.last_hat_count = self.af["hat_count"]
        self.last_snare_count = self.af["snare_count"]

    def tick(self, colors=[(0, 0, 0)], audio_features=None):
        self.set_audio_features(audio_features)
        self.pattern_manager.update(self.fixtures, audio_features, colors)
        for f in self.fixtures:
            f.update()

        buffer = self.outputs.get_buffer()
        for f in self.fixtures:
            start_channel = f.config.address.dmx_start_channel - 1
            buffer[f.config.address.universe - 1][
                start_channel : start_channel + len(f.CHANNELS)
            ] = f.get_channel_values()
        self.outputs.write(buffer)


if __name__ == "__main__":
    engine = LightEngine()
    import numpy as np

    while True:
        c = [
            np.cos(time.time()) * 0.5 + 0.5,
            0.5 + 0.5 * np.cos(time.time() + 2.0),
            0.5 + 0.5 * np.cos(time.time() + 4.0),
        ]
        engine.tick(
            colors=c,
            audio_features={
                "hat_count": 0,
                "snare_count": 0,
                "kick_count": 0,
                "smooth_low": 0.001,
                "on_tempo": 0,
            },
        )
        time.sleep(1 / 60)
    exit(0)
