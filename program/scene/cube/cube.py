import numpy as np
from matplotlib.colors import rgb_to_hsv, hsv_to_rgb
from program.prog_base import FragmentBase


class Cube(FragmentBase):
    def __init__(self, **kwargs):
        super().__init__("Cube", **kwargs)
        self.init_params()

    def init_params(self):
        self.program["go_rot"] = 0.0
        self.program["deep"] = 0.0
        self.smooth_fast = 1
        self.smooth_mid = 1
        self.smooth_tmp = 1
        self.color = np.array([1.0, 0.58, 0.29])
        self.deep_tic = 0.05
        self.go_rot = 0.0
        self.face = 1.0

    def update_params(self, fa):
        tmp = rgb_to_hsv(self.color)
        tmp[0] += 0.002
        tmp[0] = tmp[0] % 1
        self.color = hsv_to_rgb(tmp)

        self.smooth_fast = self.smooth_fast * 0.2 + 0.8 * fa["low"][3]
        self.smooth_mid = self.smooth_mid * 0.2 + 0.8 * fa["low"][2]
        tmp = max(self.smooth_fast - self.smooth_mid * 0.95, 0) * 3
        self.smooth_tmp = 0.5 * self.smooth_tmp + 0.5 * tmp

        if fa["on_chill"]:
            self.deep_tic += 0.01
        else:
            self.deep_tic -= 0.2
        self.deep_tic = np.clip(self.deep_tic, 0.0, 2.0)

        if fa["on_kick"]:
            self.go_rot += np.pi / 2.0 * 0.08
            self.face = np.random.randint(1, 4) * (-1) ** np.random.randint(1, 3)

        self.go_rot = np.pi / 2 * (1.0 - (fa["decaying_kick"]))

    def get_uniform(self, fa):
        super().get_uniform(fa)
        self.program["iTime"] = fa["time"] / 2
        self.program["energy_fast"] = (
            np.log(self.smooth_tmp + 1.0) * fa["bpm"] / 75 + self.deep_tic
        )
        self.program["energy_mid"] = (fa["low"][2] + self.smooth_fast * 2.0) / 2.0
        self.program["color"] = self.color * 0.7
        self.program["go_rot"] = self.go_rot
        self.program["face"] = self.face
        self.program["deep"] = self.deep_tic * 2.0
