import math
import time

import numpy as np

from light_new.fixture import LightString
from light_new.patterns.base import Pattern


def map_smooth_low_vertical(string: LightString, af, bind, color, pos_s=None, pos_e=None):
    length = string.config.length
    pixels = np.zeros((length, 3))
    f0 = 1.5
    dim = 0.75
    alpha = np.sin(time.time() + pos_s[0] * 3.14159 * af["on_tempo32"]) * 0.5 + 0.5
    lfo = np.sin(time.time() + pos_s[0] * 3.14159 * f0) * (0.5 + 0.5) * 0.5 + 0.5
    lfo = lfo * 0.75 * (1 - alpha) + alpha
    v = np.linspace(0, 8, 8) * (1 - lfo)
    pixels[:, 0] = (v < af["smooth_low"] * 3.0) * af["smooth_low"] ** 0.5 * 2.0
    pixels[:] = pixels[:, 0].reshape(-1, 1)
    return pixels * color * dim


def tempo_2(string: LightString, af, bind, color, pos_s, pos_e):
    control_width = bind("F0", 0.1, 2)  # min 0.0001 max 1
    length = string.config.length
    pos_2d = np.linspace(pos_s, pos_e, length)
    pixels = np.zeros((length, 3))
#   pos_2d_y_offset = 1 - abs(pos_2d[:, 0]) * 0.2
#   pos_2d[:, 1] += pos_2d_y_offset
    t = math.sin(af["on_tempo2"] * 2 * 3.1415)
    amplitude = np.clip(0, 1, 1 - abs(pos_2d[:, 1] - t) / control_width) ** 0.5
    pixels[:] = color
    return pixels * amplitude.reshape(-1, 1)


class Ok:
    def __init__(self):
        self.count = 0
        self._updated = False
        self.dim = 0
        self.t = time.time()

    def __update(self, af):
        if (time.time() - self.t) > 1 / 120:
            self.t = time.time()
            self._updated = False

        if self._updated:
            return

        if af["on_kick"]:
            self.count += 1
            self.count %= 4
            self.dim = 0.25 + 0.75 * (1.0 - (self.count + 1) * 0.25)

        self._updated = True

    def __call__(self, string, af, bind, color, pos_s, pos_e):
        self.__update(af)
        length = string.config.length
        pixels = np.zeros((length, 3))
        pow_ = bind("F0", 0.25, 4.0)
        scale = bind("F1", 0.5, 2.0)

        if pos_s[2] < 1 or pos_e[2] < 1:
            pixels[:, 0] = af["decaying_kick"] * self.dim**pow_ * scale

        if abs(pos_e[0]) - 0.1 < (self.count + 1) * 0.25:
            pixels[:, 0] = af["decaying_kick"] * (
                self.dim + abs(pos_e[0]) ** pow_ * scale
            )

        return pixels**pow_ * scale


class Chill1(Pattern):
    def __init__(self):
        super().__init__()
        self.count = 0
        self._updated = False
        self.chill = 0
        self.t = time.time()
        self.N_string = {}
        self.wait = 0
        self.decay_rate = 0.75

    def __update(self, af, string, color):
        if len(self.N_string) < 16:
            self.N_string[string.config.name] = 0

        wait_time = 8
        pow_ = self.map("F0", 0.5, 4)
        decay_rate = self.map("F1", 0.5, 0.95)

        if self.wait > 16 * wait_time:
            self.N_string[string.config.name] = np.random.rand(8) ** pow_

            if string.config.name == "octostrip 2 strip 8":
                self.wait = 0

        self.wait += 1
        self.N_string[string.config.name] *= decay_rate
        alpha = self.map("F2", 0.0, 1.0)
        self.color = color * alpha + (1 - alpha)

    def pattern(self, string, af, color, pos_s, pos_e):
        self.__update(af, string, color)
        length = string.config.length
        pixels = np.zeros((length, 3))
        pixels[:, 0] = self.N_string[string.config.name]
        pixels[:] = pixels[:, 0].reshape(-1, 1) * self.color
        return pixels


def middleboom(string, af, bind, color, pos_s, pos_e):
    length = string.config.length
    pixels = np.zeros((length, 3))
    sigma = bind("F0", 0.001, 0.01)
    offset = bind("F1", 0.1, 0.6)
    pow_ = bind("F2", 0.25, 8.0)
    tmp = np.array([4, 3, 2, 1, 1, 2, 3, 4]) - 0.5
    tmp = np.exp(
        -(tmp * tmp) * sigma * (abs(pos_s[0]) ** pow_ + offset) / af["smooth_low"]
    )
    pixels = color * tmp.reshape(-1, 1)
    return pixels


def chill2(string, af, bind, color, pos_s, pos_e):
    length = string.config.length
    pixels = np.zeros((length, 3))
    pos_lin = np.linspace(pos_s, pos_e, length)
    tone_mapping_lin = bind("F0", 0.0, 2.0)
    tone_mapping_pow = bind("F1", 0.2, 8.0)
    amp_kick = bind("F2", 0.0, 2.0)

    if pos_s[2] == 1:
        lfox = (
            np.sin(
                af["on_tempo4"] * 2.0 * 3.14159
                + pos_lin[:, 0] * 3.14159
                + af["smooth_low"] * amp_kick
            )
            * 0.5
            + 0.5
        )
        lfoy = (
            np.sin(
                af["on_tempo8"] * 2.0 * 3.14159
                + pos_lin[:, 1] * 3.14159
                + af["smooth_low"] * amp_kick
            )
            * 0.5
            + 0.5
        )
        pixels[:, 0] = lfox * lfoy  # *lfoz
    elif pos_s[0] == 0.0:
        pos_lin = (pos_lin - np.min(pos_lin, 0)) / (
            np.max(pos_lin, 0) - np.min(pos_lin, 0) + 1e-8
        ) * 2.0 - 1.0
        lfox = (
            np.sin(
                -np.sign(pos_e[0]) * af["on_tempo4"] * 2.0 * 3.14159
                - pos_lin[:, 0]
                + (np.sign(pos_e[0]) + 1) * 0.5 * 3.14159
            )
            * 0.5
            + 0.5
        )
        pixels[:, 0] = lfox
    else:
        pos_lin = (pos_lin - np.min(pos_lin, 0)) / (
            np.max(pos_lin, 0) - np.min(pos_lin, 0) + 1e-8
        ) * 2.0 - 1.0
        lfoy = (
            np.sin(-np.sign(pos_e[2]) * af["on_tempo4"] * 2.0 * 3.14159 - pos_lin[:, 2])
            * 0.5
            + 0.5
        )
        pixels[:, 0] = lfoy

    pixels[:] = pixels[:, 0].reshape(-1, 1)
    return (pixels * color * tone_mapping_lin) ** tone_mapping_pow


class OnKickSin(Pattern):
    def __init__(self):
        super().__init__()
        self.cumul = 0
        self.sens = 1.0
        self.f0 = 1
        self.on_mini_chill = 0
        self.wait_next = 0
        self.tone_mapping_lin = 0.8
        self.tone_mapping_pow = 2.0
        # TODO: MINI CHILL CHANGE DE PRESET MAIS PAS POUR LUI
        self._use_mini_chill = False

    def update(self, af, color):
        if af["mini_chill"] and self.wait_next > 5 and not af["on_chill"]:
            self.sens *= -1
            self.wait_next = 0

        self.wait_next += 1 / 60

        cumul_count = self.map("F0", 0.05, 0.3)
        cumul_count_nrj = self.map("F1", -0.2, 0.2)

        self.cumul += (
            cumul_count_nrj * af["smooth_low"] * 2.0 + cumul_count * 0.05
        ) * self.sens

    def pattern(self, string, af, color, pos_s, pos_e):
        length = string.config.length
        pixels = np.zeros((length, 3))
        pos_lin = np.linspace(pos_s, pos_e, length)

        if pos_s[2] == 1:
            lfox = (
                np.sin(self.cumul * 2.0 * 3.14159 + pos_lin[:, 0] * 3.14159) * 0.5 + 0.5
            )
            lfoy = (
                np.sin(self.cumul * 2.0 * 3.14159 + pos_lin[:, 1] * 3.14159) * 0.5 + 0.5
            )
            pixels[:, 0] = lfox * lfoy  # *lfoz
        elif pos_s[0] == 0.0:
            pos_lin = (pos_lin - np.min(pos_lin, 0)) / (
                np.max(pos_lin, 0) - np.min(pos_lin, 0) + 1e-8
            ) * 2.0 - 1.0
            lfox = (
                np.sin(
                    -np.sign(pos_e[0]) * self.cumul * 2.0 * 3.14159
                    - pos_lin[:, 0]
                    + (np.sign(pos_e[0]) + 1) * 0.5 * 3.14159
                )
                * 0.5
                + 0.5
            )
            pixels[:, 0] = lfox
        else:
            pos_lin = (pos_lin - np.min(pos_lin, 0)) / (
                np.max(pos_lin, 0) - np.min(pos_lin, 0) + 1e-8
            ) * 2.0 - 1.0
            lfoy = (
                np.sin(-np.sign(pos_e[2]) * self.cumul * 2.0 * 3.14159 - pos_lin[:, 2])
                * 0.5
                + 0.5
            )
            pixels[:, 0] = lfoy

        pixels[:] = color * pixels[:, 0].reshape(-1, 1)
        return (pixels * self.tone_mapping_lin) ** self.tone_mapping_pow


def mix(color_a, color_b, ratio):
    return color_a * ratio + color_b * (1 - ratio)


class Ascent(Pattern):
    def __init__(self):
        super().__init__()
        self.count = 0

    def update(self, af, color):
        f0 = self.map("K0", -1, 1)  # TODO GOOD PARAMS
        f0 = self.map("F0", -10, 10)  # TODO GOOD PARAMS
        f1 = self.map("F1", -1, 1)
        self.count += 1 / 60 * f0
        self.count += f1 * af["smooth_low"] ** 2

    def pattern(self, string: LightString, af, color, pos_s, pos_e):
        length = string.config.length
        pixels = np.zeros((length, 3))
        pixels[:] = color
        f2 = self.map("F2", 1, 4)
        pos_3d = np.linspace(
            string.config.position_start, string.config.position_end, length
        )
        f3 = self.map("F3", 0, 1)
        k3 = self.map("K3", -10, 10)
        k11 = self.map("K11", -10, 10)
        width = f2
        y = pos_3d[:, 1]
        y += f3 * k3 * abs(pos_3d[:, 0])
        y += f3 * k11 * abs(pos_3d[:, 2])
        pixels *= np.sin(self.count + y.reshape(-1, 1) * width)
        return pixels


class Alternate(Pattern):
    def __init__(self):
        super().__init__()
        self._updated = False
        self.count = 0
        self.count3 = 0
        self.count5 = 0
        self.t = time.time()

    def __update(self, af):
        if (time.time() - self.t) > 1 / 120:
            self.t = time.time()
            self._updated = False

        if self._updated:
            return

        if af["on_kick"]:
            self.count += 1
            self.count %= 2
            self.count3 += 1
            self.count3 %= 3
            self.count5 += 1
            self.count5 %= 5
            print(self.count5 % 2)

        self._updated = True

    def pattern(self, string, af, color, pos_s, pos_e):
        self.__update(af)
        length = 8
#       L = np.linspace(pos_s, pos_e, length)
        pixels = np.zeros((length, 3))
        choice = self.map("F0", 0, 3)

        if choice < 1:
            pixels[:] = abs(self.count - (pos_e[0] > 0))
        elif choice < 2:
            pixels[:] = abs(self.count - (pos_s[2] < 1))
        elif choice < 3:
            pixels[:] = abs(self.count - (pos_s[2] < 1)) * abs(
                self.count3 % 2 - (pos_e[0] > 0)
            )
        elif choice < 4:
            pixels[:] = abs(self.count - (pos_s[2] < 1)) * abs(
                self.count5 % 2 - (pos_e[0] > 0)
            )

        pixels *= color
        return pixels


class LambdaPattern(Pattern):
    def __init__(self, fun):
        super().__init__()
        self.pattern_fun = fun

    def pattern(
        self,
        fixture: LightString,
        af: dict,
        color: np.ndarray,
        pos_s,
        pos_e,
    ) -> np.ndarray:
        return self.pattern_fun(fixture, af, self.map, color, pos_s, pos_e)

    def __str__(self) -> str:
        if hasattr(self.pattern_fun, "__name__"):
            return self.pattern_fun.__name__

        return str(self.pattern_fun)
