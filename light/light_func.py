import random

import numpy as np

from datetime import datetime, timedelta


def lightKick(color, af, size):
    res = np.array((size, 3))
    res = np.ones((size, 3)) * color.reshape(1, -1)
    res = res * af["smooth_low"]

    if np.max(res) > 1.0:
        res /= np.max(res)

    return res


def symetry(half_pattern, color, af, size):
    if size % 2:
        print("size for symetric pattern is not even")

    half = half_pattern(color, af, size=size // 2)
    data = np.concatenate((half, np.flip(half, axis=0)))
    return data


class Kickwav:
    def __init__(self, symetry: bool):
        self.buff = None
        self.mode = "slow"
        self.symetry_mode = symetry
        self.shift_step = 1 if self.mode == "slow" else 2

    def kickwav(self, color, af, size):
        if self.buff is None:
            self.buff = np.zeros((size, 3))

        self.buff[self.shift_step :] = self.buff[: -self.shift_step]
        self.buff[: self.shift_step] *= 0.9

        if af["on_kick"]:
            for i in range(self.shift_step):
                self.buff[i] = color * 0.9 ** (self.shift_step - 1 - i)

        res = np.copy(self.buff) ** 2.0
        return res

    def __call__(self, color, af, size):
        if self.symetry_mode:
            return symetry(self.kickwav, color, af, size)

        return self.kickwav(color, af, size)


class SolidStars:
    def __init__(self):
        self.buff_sprinkles = None
        self.buff_solid = None
        #       self.rng = np.random.default_rng(seed=42)
        self.count = 0
        self.last_on_tempo = 0
        self.current_color = (0.0, 0.0, 0.0)

    def __call__(self, color, af, size):
        if self.buff_sprinkles is None:
            self.buff_sprinkles = np.zeros((size, 3))

        if self.buff_solid is None:
            self.buff_solid = np.zeros((size, 3))

        self.buff_sprinkles *= 0.87

        if self.count % 5 == 0:
            new = np.zeros((size, 3))
            values = np.random.rand(size)
            new[values > 0.93] = (1.0, 1.0, 1.0)
            self.buff_sprinkles = np.maximum(self.buff_sprinkles, new)
            self.count = 0

        self.count += 1

        if self.last_on_tempo < af["on_tempo4"]:
            self.current_color = color**2.2

        if af["mini_chill"]:
            # Perte du buff solid
            self.buff_solid *= 0.9
        else:
            self.buff_solid[:] = af["on_tempo4"] ** 2 * self.current_color
            self.last_on_tempo = af["on_tempo4"]

        return np.maximum(self.buff_solid, self.buff_sprinkles)


class RandomSpots:
    def __init__(self):
        self.buff = None
        self.current_spots = []
        self.last_on_tempo = 1.0
        self.last_i = 0
        self.last_spots = [0, 0]

    def too_close(self, i):
        # Last x current_spots ?
        return any([abs(i - spot) < 10 for spot in self.last_spots])

    def __call__(self, color, af, size):
        if self.buff is None:
            self.buff = np.zeros((size, 3))

        self.buff *= 0.97

        if af["on_kick"]:
            for spot in range(len(self.last_spots)):
                i = None

                while i is None or self.too_close(i):
                    i = random.randint(6, self.buff.shape[0] - 7)

                self.last_spots[spot] = i
                spray = np.arange(-6, 7)
                a = np.exp(-np.abs(spray) * 0.4).reshape(-1, 1)
                self.buff[i + spray] = color.reshape(1, -1) ** 2.2 * a**0.5

        return self.buff


class Pingpong:
    def __init__(self):
        self.which = 1
        self.mode = "pingpongkk"
        self.buff1 = None
        self.buff2 = None

    def __call__(self, color, af, size):
        if self.buff1 is None:
            self.buff1 = np.zeros((size // 2, 3))
            self.buff2 = np.zeros((size // 2, 3))

        self.buff1[2:] = self.buff2[:-2]
        self.buff1[:2] *= 0.9
        self.buff2[2:] = self.buff2[:-2]
        self.buff2[:2] *= 0.9

        if af["on_kick"]:
            self.which ^= 1

            if self.mode == "pingpong":
                if self.which:
                    self.buff1[0] = color * 0.9
                    self.buff1[1] = color
                else:
                    self.buff2[0] = color * 0.9
                    self.buff2[1] = color
            else:
                self.buff1[0] = color * 0.9
                self.buff1[1] = color
                self.buff2[0] = color * 0.9
                self.buff2[1] = color

        # Reshape things
        res = np.concatenate((self.buff1, self.buff2))
        res = np.copy(res) ** 2.0
        return res


class All:
    def __init__(self):
        self.lightKick = lightKick
        self.kickwav = Kickwav(symetry=False)
        self.random_spots = RandomSpots()
        self.solid_stars = SolidStars()
        self.pingpong = Pingpong()
        self._patterns = [
            lightKick,
            self.kickwav,
            self.random_spots,
            #           self.pingpong
            ## Disabled pingpong because only one led strip is addressed
            self.solid_stars,
        ]
        self._current_pattern_index = 0
        self._last_pattern_change = datetime.now()
        self._will_change_pattern = False

    def change_pattern(self):
        self._last_pattern_change = datetime.now()
        self._current_pattern_index += 1

        # Reset if out of bounds
        if self._current_pattern_index == len(self._patterns):
            self._current_pattern_index = 0
        print(
            "changed patalight pattern to {}".format(
                ["lightKick", "kickwav", "random spots", "solid stars"][
                    self._current_pattern_index
                ]
            )
        )

    @property
    def current_pattern(self):
        return self._patterns[self._current_pattern_index]

    def tick(self, af):
        if (datetime.now() > self._last_pattern_change + timedelta(minutes=2)) and af[
            "mini_chill"
        ]:
            self._will_change_pattern = True

        if self._will_change_pattern and not af["mini_chill"]:
            self.change_pattern()
            self._will_change_pattern = False
