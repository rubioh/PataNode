import usb.core
import usb.util
import time
import os
import yaml
import colorsys
from math import cos
import numpy as np
from light.device import LightDevice
import light.fixture
from light.fixture.config import LIGHT_MODELS
from light.shader_mapper import ShaderMapper
import time

print(LIGHT_MODELS)


class TimedEvent:
    def __init__(self):
        self.duration = -1e10
        self.start = 0

    def activate(self, duration_seconds):
        self.start = time.time()
        self.duration = duration_seconds

    def activate_10(self):
        self.activate(10)

    def __call__(self):
        return (time.time() > self.start) and (time.time() < self.start + self.duration)


class LightEngine:
    def __init__(self, args, sceno_path: str = None):
        self.shader_buffer = [
            0.0,
        ] * 512
        self.use_shader_buffer = args.use_shader_buffer
        self.USB_VID = 0xCAFE
        self.DMX_CHANNELS_NUM = 512

        self.light_device = LightDevice(args)
        self.force_strobe = TimedEvent()
        self.lights = list()

        self.load_sceno(sceno_path)
        self.init_shader_light_binding()

        self.wait = 0
        self.prev_ts = time.time()

    def load_sceno(self, path: str):
        if path is None:
            path = "light/sceno/2triangle4par.yaml"
        #            path = "light/sceno/plante_a_son.yaml"
        sceno = yaml.safe_load(open(path, "r"))
        for light_name, infos in sceno.items():
            print(light_name)
            self.add_light(light_name, infos)

    def add_light(self, light_name: str, infos: dict):
        light = LIGHT_MODELS[infos["type"]](infos)
        self.lights.append(light)

    def init_shader_light_binding(self):
        self.shader_mapper = ShaderMapper(self)
        for light in self.lights:
            self.shader_mapper.add_light(light)

    def __call__(self, color=(0, 0, 0), audio_features=None):
        af = audio_features
        output_buffer = list(np.zeros((512)))

    def __call__(self, color=(0, 0, 0), audio_features=None):
        af = audio_features
        output_buffer = list(np.zeros((512)))
        for light in self.lights:
            light_buffer = light.get_dmx_buffer()
            output_buffer[light.dmx_address : light.dmx_address + len(light_buffer)] = (
                light_buffer
            )
        if self.use_shader_buffer:
            for i, x in enumerate(self.shader_buffer):
                output_buffer[i] = x
        self.wait += 1
        self.wait %= 102
        #        if self.wait == 30:
        #           print(output_buffer)
        self.light_device.write(output_buffer)
