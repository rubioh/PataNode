import time

import numpy as np
import usb.core # type: ignore[import-untyped]
import usb.util # type: ignore[import-untyped]

from light.light_func import All


class LightEngine:
    def __init__(self):
        self.USB_VID = 0xcafe
        self.DMX_CHANNELS_NUM = 512
        self.NUM_PIXELS = 150  # Number of ball in pataguirlande
        self.init_usb_device()
        self.func = All()
        self.wait = 0


    def init_usb_device(self):
        self.dev = usb.core.find(idVendor=0x0000, idProduct=0x0001)

        if self.dev is None:
            print('No patalight gros noob')
        else:
            print('connecting to patalight')
            self.cfg = self.dev.get_active_configuration()
            intf = self.cfg[(0,0)]

            self.outep = usb.util.find_descriptor(
                    intf,
                    custom_match= \
                            lambda x: \
                                usb.util.endpoint_direction(x.bEndpointAddress) == \
                                usb.util.ENDPOINT_OUT)

            assert self.outep is not None
            print('connected to patalight')

        # USB FPS
        self.prev_ts = time.time()

    def to_bytes(self, data, data_par):
        # data size (N, 3)
        if data.shape[0]>self.DMX_CHANNELS_NUM//3:
            data = data[:self.DMX_CHANNELS_NUM]

        flat = np.zeros(512)
        flat[0:3] = data_par
        flat[15:18] = data_par
        data = data.flatten()
        flat[49:49 + data.shape[0]] = data.flatten()
        numpy_char = 'u1'
        flat *= np.iinfo(numpy_char).max
        return flat.astype(numpy_char).tobytes()

    def get_color_par(self, color, af):
        res = color * af['smooth_low']

        if np.max(res) > 1.:
            res /= np.max(res)
        return res

    def get_colors(self, color, af):
        # Color is a np array of shape 3
        return self.func.current_pattern(color, af, size=self.NUM_PIXELS)
#       return np.ones((self.NUM_PIXELS, 3)) * np.array(color).reshape(1,-1)

    def __call__(self, color=(0,0,0), audio_features=None):
        af = audio_features

        self.func.tick(af)
        data = self.get_colors(color, af)
        data_par = self.get_color_par(color, af)
        byte_array = self.to_bytes(data, data_par)

        if self.dev is None:
            return

        self.outep.write(byte_array)
        self.prev_ts = time.time()
