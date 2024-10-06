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

class LightEngine:

    def __init__(self, sceno_path: str = None):
        self.USB_VID = 0xCAFE
        self.DMX_CHANNELS_NUM = 512

        self.light_device = LightDevice()

        self.lights = list()

        self.load_sceno(sceno_path)

        self.wait = 0
        self.prev_ts = time.time()

    def load_sceno(self, path: str):
        if path is None:
            path = "light/sceno/plante_a_son.yaml"   
        sceno = yaml.safe_load(open(path, "r"))
        for light_name, infos in sceno.items():
            self.add_light(light_name, infos)

    def add_light(self, light_name: str, infos: dict):
        light = LIGHT_MODELS[light_name](infos)
        self.lights.append(light)

    def __call__(self, color=(0, 0, 0), audio_features=None):
        af = audio_features
        output_buffer = np.zeros((512))
        for light in self.lights:
            light.update([1.,0.,0.])
            light_buffer = light.get_dmx_buffer()
            output_buffer[light.dmx_address:light.dmx_address+len(light_buffer)] = light_buffer
        self.light_device.write(output_buffer)
