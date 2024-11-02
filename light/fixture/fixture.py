import numpy as np

class Fixture():
    MODEL: str
    CHANNELS: dict[str, int]
    CHANNELS_DEFAULTS: dict[str, float]
    attrib: dict[str, float]

    def __init__(self, infos) -> None:
        self.init_address(infos["address"])
        self.init_position(infos["position"])
        self.init_shader_binding(infos)
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

    def init_address(self, address_infos: dict):
        self.universe = address_infos["universe"]
        self.dmx_address = address_infos["dmx_address"]-1

    def init_position(self, position_infos: list):
        self.position = position_infos

    def init_shader_binding(self, infos: dict):
        if "shader_binding" in infos.keys():
            shader_binding = infos["shader_binding"]
            self.use_shader = True
            self.canvas_position = shader_binding["canvas_position"]
            self.num_pixels = shader_binding["num_pixels"]
        else:
            self.use_shader = False

    def get_dmx_buffer(self):
        dmx_buffer = [0]*len(self.CHANNELS)
        for name, idx in self.CHANNELS.items():
            dmx_buffer[idx-1] = self.attrib[name]
        return dmx_buffer

    def __str__(self):
        return f"Name : {self.MODEL} \tUniverse : {self.universe}, Address : {self.dmx_address+1} \n"
