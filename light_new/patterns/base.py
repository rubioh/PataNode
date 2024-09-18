from light_new.fixture import LightString

import numpy as np
import abc
import colorsys


def bubble_effect(string: LightString, af, bind, pixels):
    bubble_range = bind("F4", 0.1, 1)
    amplitude_min = bind("K4", 0, 1)
    bubble_curve = bind("K12", -1, 1)
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


class Pattern(abc.ABC):
    def __init__(self):
        self.strips = None
        self.mapped = {}

    @abc.abstractmethod
    def pattern(
        self,
        fixture: LightString,
        af: dict,
        color: np.ndarray,
        pos_s,
        pos_e,
    ) -> np.ndarray: ...

    def map(self, uid, *args):
        self.mapped[uid] = True
        return self._ctrl.bind_to_controller(uid, *args)

    def update(self, af: dict, color: np.ndarray):
        pass

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

    def tone_map(self, pattern, ctrl, color):
        pattern *= ctrl.bind_to_controller("K5", 1, 5)
        pattern **= ctrl.bind_to_controller("K13", 0.25, 4)
        pattern = np.tanh(pattern)
        alpha = ctrl.bind_to_controller("K21", 0.0, 1.0)
        pattern = pattern * alpha + (1 - alpha)
        return pattern

    def render(self, strips: list[LightString], af, ctrl) -> np.ndarray:
        return
        self._ctrl = ctrl
        color = np.array(colorsys.hsv_to_rgb(ctrl.bind_to_controller("F5", 0, 1), 1, 1))
        self.update(af, color)
        if self.strips is None:
            self.get_normalized_pos(strips)
        for i, f in enumerate(strips):
            pattern = self.pattern(f, af, color, self.pos_start[i], self.pos_end[i])
            pattern = self.tone_map(pattern, ctrl, color)
            pattern = bubble_effect(f, af, self.map, pattern)
            f.set_pixels(pattern)
        return color

    def __str__(self) -> str:
        return self.__class__.__name__
