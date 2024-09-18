from light_new.fixture import Fixture, Lyre, LightString, Z1020
from light_new.cracra import Cracra

import numpy as np
import time
import math
import abc

from controller.launch_control_xl import LaunchControlMidiReceiver, ButtonEvent


def blackout(length: int):
    return np.zeros(
        (length, 3),
    )


def dimm(length: int):
    a = np.zeros(
        (length, 3),
    )
    a[:, 0] = np.linspace(0, 1, length)
    a[:, 2] = np.linspace(1, 0, length)
    return a


def sine(string: LightString):
    length = string.config.length

    pos_2d = np.linspace(
        string.config.position_start, string.config.position_end, length
    )

    z = pos_2d[:, 2]
    fz = np.sin(z * math.pi + time.monotonic())
    y = pos_2d[:, 1] * 4
    pixels = np.zeros((length, 3))
    pixels[:, 0] = abs(fz - y)
    return pixels


def map_smooth_low(string: LightString, af, pos_s=None, pos_e=None):
    length = string.config.length

    pos_2d = np.linspace(pos_s, pos_e, length)
    pixels = np.zeros((length, 3))
    pixels[:, 0] = ((1.0 - af["decaying_kick"]) < (abs(pos_2d[:, 0]) + 0.05)) * (
        1.0 - abs(pos_2d[:, 0])
    )
    return pixels


def map_smooth_low_vertical(string: LightString, af, pos_s=None, pos_e=None):
    length = string.config.length
    pixels = np.zeros((length, 3))

    f0 = 1.5
    dim = 0.75
    alpha = np.sin(time.time() + pos_s[0] * 3.14159 * af["on_tempo32"]) * 0.5 + 0.5
    lfo = np.sin(time.time() + pos_s[0] * 3.14159 * f0) * (0.5 + 0.5) * 0.5 + 0.5
    lfo = lfo * 0.75 * (1 - alpha) + alpha

    v = np.linspace(0, 8, 8) * (1 - lfo)
    pixels[:, 0] = (v < af["smooth_low"] * 3.0) * af["smooth_low"] ** 0.5 * 2.0
    return pixels * dim


def tempo_2(string: LightString, af, ctrl, pos_s, pos_e):
    control_width = ctrl.bind_to_controller("F0", 0.1, 2)  # min 0.0001 max 1

    length = string.config.length
    pos_2d = np.linspace(pos_s, pos_e, length)
    pixels = np.zeros((length, 3))

    # pos_2d_y_offset = 1 - abs(pos_2d[:, 0]) * 0.2

    # pos_2d[:, 1] += pos_2d_y_offset

    t = math.sin(af["on_tempo2"] * 2 * 3.1415)

    pixels[:, 0] = np.clip(0, 1, 1 - abs(pos_2d[:, 1] - t) / control_width) ** 0.5
    return pixels


class OK:
    def __init__(self):
        self.count = 0
        self._updated = False
        self.dim = 0
        self.t = time.time()

    def update(self, af):
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

    def __call__(self, string, af, pos_s, pos_e):
        self.update(af)
        length = string.config.length
        pixels = np.zeros((length, 3))

        if pos_s[2] < 1 or pos_e[2] < 1:
            pixels[:, 0] = af["decaying_kick"] * self.dim
        if abs(pos_e[0]) - 0.1 < (self.count + 1) * 0.25:
            pixels[:, 0] = af["decaying_kick"] * (self.dim + abs(pos_e[0]) ** 2 * 0.75)
        return pixels


class Chill1:
    def __init__(self):
        self.count = 0
        self._updated = False
        self.chill = 0
        self.t = time.time()
        self.N_string = {}
        self.wait = 0
        self.pow = 2
        self.wait_time = 8
        self.decay_rate = 0.75

    def update(self, af, string=None):
        if len(self.N_string) < 16:
            self.N_string[string.config.name] = 0
        if self.wait > 16 * self.wait_time:
            self.N_string[string.config.name] = np.random.rand(8) ** self.pow
            if string.config.name == "octostrip 2 strip 8":
                self.wait = 0
        self.wait += 1
        self.N_string[string.config.name] *= self.decay_rate

    def __call__(self, string, af, pos_s, pos_e):
        self.update(af, string)
        length = string.config.length
        pixels = np.zeros((length, 3))
        pixels[:, 0] = self.N_string[string.config.name]
        return pixels


def chill2(string, af, pos_s, pos_e):
    length = string.config.length
    pixels = np.zeros((length, 3))
    pos_lin = np.linspace(pos_s, pos_e, length)

    tone_mapping_lin = 0.8
    tone_mapping_pow = 2.0

    if pos_s[2] == 1:
        lfox = (
            np.sin(af["on_tempo4"] * 2.0 * 3.14159 + pos_lin[:, 0] * 3.14159) * 0.5
            + 0.5
        )
        lfoy = (
            np.sin(af["on_tempo8"] * 2.0 * 3.14159 + pos_lin[:, 1] * 3.14159) * 0.5
            + 0.5
        )
        pixels[:, 0] = lfox * lfoy  # *lfoz
    elif pos_s[0] == 0.0:
        pos_lin = (pos_lin - np.min(pos_lin, 0)) / (
            np.max(pos_lin, 0) - np.min(pos_lin, 0)
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
            np.max(pos_lin, 0) - np.min(pos_lin, 0)
        ) * 2.0 - 1.0
        lfoy = (
            np.sin(-np.sign(pos_e[2]) * af["on_tempo4"] * 2.0 * 3.14159 - pos_lin[:, 2])
            * 0.5
            + 0.5
        )
        pixels[:, 0] = lfoy
    return (pixels * tone_mapping_lin) ** tone_mapping_pow


class OnKickSin:
    def __init__(self):
        self._updated = False
        self.cumul_count = 0.01
        self.cumul = 0
        self.sens = 1.0
        self.frequency = 1.0
        self.f0 = 1
        self.on_mini_chill = 0
        self.wait_next = 0
        self.tone_mapping_lin = 0.8
        self.tone_mapping_pow = 2.0
        self.t = time.time()
        # TODO MINI CHILL CHANGE DE PRESET MAIS PAS POUR LUI
        self._use_mini_chill = False

    def update(self, af):
        if (time.time() - self.t) > 1 / 120:
            self.t = time.time()
            self._updated = False
        if self._updated:
            return
        if af["mini_chill"] and self.wait_next > 5 and not af["on_chill"]:
            self.sens *= -1
            self.wait_next = 0
        self.wait_next += 1 / 60 / 8

        self.frequency = 0.5  # + .25 * np.sin(time.time() * .1)
        self.f0 = self.frequency
        self.cumul += (
            self.cumul_count * af["smooth_low"] * 2.0 + self.cumul_count * 0.05
        ) * self.sens

    def __call__(self, string, af, pos_s, pos_e):
        self.update(af)
        length = string.config.length
        pixels = np.zeros((length, 3))
        pos_lin = np.linspace(pos_s, pos_e, length)
        if pos_s[2] == 1:
            lfox = (
                np.sin(self.cumul * 2.0 * 3.14159 * self.f0 + pos_lin[:, 0] * 3.14159)
                * 0.5
                + 0.5
            )
            lfoy = (
                np.sin(self.cumul * 2.0 * 3.14159 * self.f0 + pos_lin[:, 1] * 3.14159)
                * 0.5
                + 0.5
            )
            pixels[:, 0] = lfox * lfoy  # *lfoz
        elif pos_s[0] == 0.0:
            pos_lin = (pos_lin - np.min(pos_lin, 0)) / (
                np.max(pos_lin, 0) - np.min(pos_lin, 0)
            ) * 2.0 - 1.0
            lfox = (
                np.sin(
                    -np.sign(pos_e[0]) * self.cumul * 2.0 * 3.14159 * self.f0
                    - pos_lin[:, 0]
                    + (np.sign(pos_e[0]) + 1) * 0.5 * 3.14159
                )
                * 0.5
                + 0.5
            )
            pixels[:, 0] = lfox
        else:
            pos_lin = (pos_lin - np.min(pos_lin, 0)) / (
                np.max(pos_lin, 0) - np.min(pos_lin, 0)
            ) * 2.0 - 1.0
            lfoy = (
                np.sin(
                    -np.sign(pos_e[2]) * self.cumul * 2.0 * 3.14159 * self.f0
                    - pos_lin[:, 2]
                )
                * 0.5
                + 0.5
            )
            pixels[:, 0] = lfoy
        return (pixels * self.tone_mapping_lin) ** self.tone_mapping_pow


def mix(color_a, color_b, ratio):
    return color_a * ratio + color_b * (1 - ratio)


def bubble_effect(string: LightString, af, ctrl, pos_s, pos_e, pixels):
    bubble_range = ctrl.bind_to_controller("F6", 0.1, 1)
    amplitude_min = ctrl.bind_to_controller("K6", 0, 1)
    bubble_curve = ctrl.bind_to_controller("K14", -1, 1)
    length = string.config.length
    pos_3d = np.linspace(
        string.config.position_start, string.config.position_end, length
    )

    diff_origin = np.array([0.0, -0.5, 0.75])

    x, y, z = np.meshgrid([-1, 1], [-1, 1], [-1, 1])
    far_away = np.vstack([x.flatten(), y.flatten(), z.flatten()]).T
    far_away_dist = np.linalg.norm(far_away - diff_origin, ord=2, axis=1.0)
    far_away_max = np.max(far_away_dist)

    distance = np.linalg.norm(pos_3d - diff_origin, ord=2, axis=1.0) / far_away_max
    amplitude = 1 - distance / bubble_range
    amplitude = np.clip(amplitude, 0, 1)
    bubble_curve = np.interp(bubble_curve, [-1, 0, 1], [0.0001, 0.5, 3])
    amplitude = amplitude ** (1 / (2 * bubble_curve))

    amplitude = amplitude_min + amplitude * (1 - amplitude_min)

    return pixels * amplitude.reshape(-1, 1)


def master_effect(string: LightString, af, ctrl, pos_s, pos_e, pixels): ...


def breathe(string: LightString, af, ctrl, pos_s, pos_e):
    color = np.array([1, 0, 0])
    length = string.config.length
    pixels = np.zeros((length, 3))
    pixels[:] = color
    return bubble_effect(string, af, ctrl, pos_s, pos_e, pixels)


class Pattern(abc.ABC):
    def __init__(self):
        self.strips = None

    @abc.abstractmethod
    def pattern(
        self,
        fixture: LightString,
        af: dict,
        ctrl: LaunchControlMidiReceiver,
        pos_s,
        pos_e,
    ) -> np.ndarray: ...

    def get_normalized_pos(self, strips: list[LightString]):
        self.strips = strips
        pos_start = np.array([f.config.position_start for f in self.strips])
        pos_end = np.array([f.config.position_end for f in self.strips])

        max_x = max(np.max(pos_start[:, 0]), np.max(pos_end[:, 0]))
        min_x = min(np.min(pos_start[:, 0]), np.min(pos_end[:, 0]))
        max_y = max(np.max(pos_start[:, 1]), np.max(pos_end[:, 1]))
        min_y = min(np.min(pos_start[:, 1]), np.min(pos_end[:, 1]))
        max_z = max(np.max(pos_start[:, 2]), np.max(pos_end[:, 2]))
        min_z = min(np.min(pos_start[:, 2]), np.min(pos_end[:, 2]))

        min_ = np.array([min_x, min_y, min_z])
        max_ = np.array([max_x, max_y, max_z])
        self.pos_start = (pos_start - min_) / (max_ - min_) * 2 - 1
        self.pos_end = (pos_end - min_) / (max_ - min_) * 2 - 1

    def render(self, strips: list[LightString], af, ctrl):
        if self.strips is None:
            self.get_normalized_pos(strips)
        for i, f in enumerate(strips):
            f.set_pixels(self.pattern(f, af, ctrl, self.pos_start[i], self.pos_end[i]))


class LambdaPattern(Pattern):
    def __init__(self, fun):
        super().__init__()
        self.pattern_fun = fun

    def pattern(
        self,
        fixture: LightString,
        af: dict,
        ctrl: LaunchControlMidiReceiver,
        pos_s,
        pos_e,
    ) -> np.ndarray:
        return self.pattern_fun(fixture, af, ctrl, pos_s, pos_e)


class LegacyLambdaPattern(LambdaPattern):
    def __init__(self, fun):
        super().__init__(lambda a, b, ctrl, d, e: fun(a, b, d, e))


class MasterEffect:
    def update(self, ctrl, cracras: list[Cracra], smoke: list[Z1020]):
        dimm = ctrl.bind_to_controller("F7", 0, 1)
        smoke_on = ctrl.bind_to_controller("K7", -1, 1) > 0
        strobe = ctrl.bind_to_controller("K15")
        strobe = ctrl.bind_to_controller("K23")
        for c in cracras:
            for i in range(8):
                # TODO: c'est cense afficher qqchose dans previs ?
                c.pixels[i][0] = dimm
                c.pixels[i][1] = strobe
        for s in smoke:
            s.attrib["enable"] = 1 if smoke_on else 0
            # TODO: auto turn on and off based on value ?


class PatternManager:
    def __init__(self):
        self.master_effect = MasterEffect()
        on_kick_sin = OnKickSin()
        ok = OK()
        chill1 = Chill1()
        self.patterns = [
            LambdaPattern(breathe),
            LegacyLambdaPattern(map_smooth_low_vertical),
            LegacyLambdaPattern(on_kick_sin),
            LegacyLambdaPattern(chill2),
            LambdaPattern(tempo_2),
            LegacyLambdaPattern(chill1),
            LegacyLambdaPattern(ok),
        ]
        self.current_pattern_index = 1

        self.try_open_launch_control()

    def change_pattern(self, incr=1):
        self.current_pattern_index += incr
        self.current_pattern_index %= len(self.current_pattern_index)
        print(f"changed pattern to {self.current_pattern}")

    def try_open_launch_control(self):
        def make_change_pattern_cb(incr):
            def handle_button(_uid, event, _time_ms, _dur):
                if event is ButtonEvent.PRESS:
                    print("mais non")
                    self.change_pattern(incr)

            return handle_button

        self.ctrl = LaunchControlMidiReceiver()

        if self.ctrl.usable:
            try:
                self.ctrl.load_settings()
            except FileNotFoundError:
                pass
            self.ctrl.set_callback("B18", make_change_pattern_cb(-1))  # left
            self.ctrl.set_callback("B19", make_change_pattern_cb(1))  # right

    @property
    def current_pattern(self):
        return self.patterns[self.current_pattern_index]

    def update(self, fixtures: list[Fixture], af):
        light_strings = list[LightString]()
        cracras = list[Cracra]()
        smoke = list[Z1020]()
        for i, f in enumerate(fixtures):
            if isinstance(f, Lyre):
                f.lookAt([3, 1, 3])
            elif isinstance(f, LightString):
                light_strings.append(f)
            elif isinstance(f, Cracra):
                cracras.append(f)
            elif isinstance(f, Z1020):
                smoke.append(f)
            elif isinstance(f, LightCubeLZR):
                f.color = colors
        self.current_pattern.render(light_strings, af, self.ctrl)
        self.master_effect.update(self.ctrl, cracras, smoke)
