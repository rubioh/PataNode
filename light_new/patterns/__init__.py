from light_new.fixture import Fixture, Lyre, LightString, Z1020, Par2Brod, LightCubeLZR
from light_new.cracra import Cracra

import pickle
import enum
import numpy as np
import time

from controller.launch_control_xl import (
    LaunchControlMidiReceiver,
    ButtonEvent,
    LEDColor,
)
from light_new.patterns.patterns import (
    LambdaPattern,
    middleboom,
    Alternate,
    Ascent,
    map_smooth_low_vertical,
    OnKickSin,
    chill2,
    tempo_2,
    Chill1,
    Ok,
)


class MasterEffect:
    def __init__(self):
        self.blackout = False

    def update(self, ctrl, cracras: list[Cracra], smoke: list[Z1020]) -> None:
        dimm = 0 if self.blackout else ctrl.bind_to_controller("F7", 0, 1)
        smoke_on = ctrl.bind_to_controller("K7", -1, 1) > 0
        strobe = ctrl.bind_to_controller("K15", 0, 1)
        for c in cracras:
            for i in range(8):
                c.pixels[i][0] = dimm
                c.pixels[i][1] = strobe
        for s in smoke:
            s.attrib["enable"] = 1 if smoke_on else 0
            # TODO: auto turn on and off based on value ?

        ctrl.set_led("K7", LEDColor.GREEN_HI if smoke_on else LEDColor.AMBER_HI)
        gradient = [LEDColor.GREEN_LO, LEDColor.GREEN_MI, LEDColor.GREEN_HI]
        ctrl.set_led(
            "K15",
            LEDColor.AMBER_HI
            if strobe <= 4 / 255
            else gradient[int(strobe * 0.9999 * len(gradient))],
        )
        ctrl.set_led("K23", LEDColor.YELLOW_MI)
        ctrl.set_led("B7", LEDColor.RED_HI if self.blackout else LEDColor.GREEN_HI)

    def toggle_blackout(self) -> None:
        self.blackout = not self.blackout


class BrodParEffect:
    def __init__(self):
        self.blackout = False

    def update(self, ctrl, par: list[Par2Brod], color: np.ndarray) -> None:
        for p in par:
            p.attrib["red"] = color[0]
            p.attrib["green"] = color[1]
            p.attrib["blue"] = color[2]
            p.attrib["dimmer"] = (
                0 if self.blackout else ctrl.bind_to_controller("F6", 0, 1)
            )
            p.attrib["uv"] = ctrl.bind_to_controller("K6", 0, 1)
            p.attrib["white"] = ctrl.bind_to_controller("K14", 0, 1)
            p.attrib["strobe"] = ctrl.bind_to_controller("K22", 0, 1)
        ctrl.set_led("B6", LEDColor.RED_HI if self.blackout else LEDColor.GREEN_HI)

    def toggle_blackout(self) -> None:
        self.blackout = not self.blackout


class VirtualControl(LaunchControlMidiReceiver):
    virtual_uid_values: dict[str, int | None]

    def __init__(self) -> None:
        self.get_pattern = lambda: None
        self.presets: dict[str, dict[int, dict[str, int | None]]] = {}
        super().__init__()
        self.virtual_uid_values = self.uid_values.copy()
        self.set_leds()

    def get_uid_values(self) -> dict[str, int | None]:
        return self.virtual_uid_values

    def handle_cc(self, cc, value):
        try:
            self.set_leds()
            uid = self.cc_to_uid.get(cc)
            if uid is not None:
                prev = self.uid_values[uid]
                super().handle_cc(cc, value)
                new = self.uid_values[uid]
                current = self.virtual_uid_values[uid]
                if prev <= current <= new or new <= current <= prev:
                    self.virtual_uid_values[uid] = self.uid_values[uid]
            else:
                print(f"unhandled midi cc {cc}, {value}")
        except Exception as e:
            print(e)
            print(e.__class__)
            raise

    def load_settings(self, file=None):
        super().load_settings(file)
        self.virtual_uid_values = self.uid_values.copy()
        self.set_leds()
        try:
            filename = "presets.pickle"
            self.presets = pickle.load(open(filename, "rb"))
        except:
            pass

    def load_preset(self, bank_id: str, slot_id: int):
        if bank_id not in self.presets:
            self.presets[bank_id] = {}
        if slot_id not in self.presets[bank_id]:
            return
        loaded_keys = [f"K{i + (i // 5) * 3}" for i in range(15)] + [
            f"F{i}" for i in range(5)
        ]
        for k, v in self.presets[bank_id][slot_id].items():
            if k in loaded_keys:
                self.virtual_uid_values[k] = v
        self.set_leds()

    def save_preset(self, bank_id: str, slot_id: int):
        if bank_id not in self.presets:
            self.presets[bank_id] = {}
        self.presets[bank_id][slot_id] = self.virtual_uid_values.copy()
        filename = "presets.pickle"
        pickle.dump(self.presets, open(filename, "wb"))

    def set_leds_knobs(self):
        pattern = self.get_pattern()
        gradient_r = [LEDColor.RED_LO, LEDColor.RED_HI, LEDColor.RED_MI]
        gradient_g = [LEDColor.GREEN_LO, LEDColor.GREEN_HI, LEDColor.GREEN_MI]

        def diff(uid):
            d = self.virtual_uid_values[uid] - self.uid_values[uid]
            if not d:
                return LEDColor.AMBER_MI
            elif d > 0:
                return gradient_r[int(d / 128 * 3)]
            elif d < 0:
                return gradient_g[int(-d / 128 * 3)]

        for i in range(3):
            for j in range(5):
                uid = f"K{8 * i + j}"
                mapped = pattern is not None and uid in pattern.mapped
                self.set_led(uid, diff(uid) if mapped else LEDColor.BLACK)

    def set_leds_buttons(self):
        pattern = self.get_pattern()
        gradient_r = [LEDColor.RED_LO, LEDColor.RED_HI, LEDColor.RED_MI]
        gradient_g = [LEDColor.GREEN_LO, LEDColor.GREEN_HI, LEDColor.GREEN_MI]

        def diff(uid):
            d = self.virtual_uid_values[uid] - self.uid_values[uid]
            if not d:
                return LEDColor.AMBER_MI
            elif d > 0:
                return gradient_r[int(d / 128 * 3)]
            elif d < 0:
                return gradient_g[int(-d / 128 * 3)]

        for i in range(6):
            mapped = pattern is not None and f"F{i}" in pattern.mapped
            self.set_led(f"B{i}", diff(f"F{i}") if mapped else LEDColor.BLACK)

    def set_leds(self):
        self.set_leds_knobs()
        self.set_leds_buttons()


class ControllerMode(enum.Enum):
    NORMAL = enum.auto()
    RECORD = enum.auto()


class PatternManager:
    def __init__(self):
        self.master_effect = MasterEffect()
        self.brod_par_effect = BrodParEffect()
        ok = Ok()
        self.patterns = [
            LambdaPattern(middleboom),
            Alternate(),
            Ascent(),
            LambdaPattern(map_smooth_low_vertical),
            OnKickSin(),
            LambdaPattern(chill2),
            LambdaPattern(tempo_2),
            Chill1(),
            LambdaPattern(ok),
        ]
        self.current_pattern_index = 0
        self.mode = ControllerMode.NORMAL
        self.current_slot: int | None = None

        self.try_open_launch_control()
        self.ctrl.get_pattern = lambda: self.current_pattern

    def change_pattern(self, incr=1) -> None:
        self.current_pattern_index += incr
        self.current_pattern_index %= len(self.patterns)
        self.current_slot = None
        self.ctrl.get_pattern = lambda: self.current_pattern
        print(f"changed pattern to {self.current_pattern}")

    def try_open_launch_control(self):
        def make_change_pattern_cb(incr):
            def handle_button(_uid, event, _time_ms, _dur):
                if event is ButtonEvent.PRESS:
                    self.change_pattern(incr)

            return handle_button

        def make_change_mode(mode):
            def handle_button(_uid, event, _time_ms, _dur):
                if event is ButtonEvent.PRESS:
                    self.mode = mode
                elif event is ButtonEvent.RELEASE:
                    self.mode = ControllerMode.NORMAL

            return handle_button

        def make_toggle(effect):
            print("hello")

            def handle_button(_uid, event, _time_ms, _dur):
                if event is ButtonEvent.PRESS:
                    effect.toggle_blackout()

            return handle_button

        self.ctrl = VirtualControl()

        if self.ctrl.usable:
            try:
                self.ctrl.load_settings()
            except FileNotFoundError:
                pass
            self.ctrl.set_callback("B18", make_change_pattern_cb(-1))  # left
            self.ctrl.set_callback("B19", make_change_pattern_cb(1))  # right
            self.ctrl.set_callback("B23", make_change_mode(ControllerMode.RECORD))
            for i in range(16):
                self.ctrl.set_callback(f"B{i}", self.handle_pad_button)

    @property
    def current_pattern(self):
        return self.patterns[self.current_pattern_index]

    def handle_pad_button(self, uid, event, _time_ms, _dur):
        pad = int(uid[1:])
        if event is ButtonEvent.PRESS:
            if uid == "B6":
                self.brod_par_effect.toggle_blackout()
            elif uid == "B7":
                self.master_effect.toggle_blackout()
            if self.mode == ControllerMode.NORMAL:
                if pad >= 8:
                    self.ctrl.load_preset(str(self.current_pattern), pad)
            elif self.mode == ControllerMode.RECORD:
                if pad >= 8:
                    self.ctrl.save_preset(str(self.current_pattern), pad)
                self.mode = ControllerMode.NORMAL

    def draw_leds(self, af) -> None:
        for uid in ["up", "down"]:
            self.ctrl.set_led(
                uid, LEDColor.RED_HI if af["on_tempo"] > 0.8 else LEDColor.BLACK
            )
        self.ctrl.set_leds_knobs()
        if self.mode == ControllerMode.NORMAL:
            self.ctrl.set_leds_buttons()
            bank = self.ctrl.presets.get(str(self.current_pattern), {})
            for i in range(8, 16):
                if i in bank:
                    self.ctrl.set_led(
                        f"B{i}",
                        LEDColor.GREEN_LO
                        if i != self.current_slot
                        else LEDColor.GREEN_HI,
                    )
                else:
                    self.ctrl.set_led(f"B{i}", LEDColor.BLACK)

        elif self.mode == ControllerMode.RECORD:
            bank = self.ctrl.presets.get(str(self.current_pattern), {})
            for i in range(8, 16):  # TODO Reindex slots on 0 instead of 8
                self.ctrl.set_led(
                    f"B{i}", LEDColor.RED_LO if i in bank else LEDColor.RED_HI
                )

    def update(self, fixtures: list[Fixture], af, colors):
        light_strings = list[LightString]()
        cracras = list[Cracra]()
        smoke = list[Z1020]()
        par = list[Par2Brod]()
        for i, f in enumerate(fixtures):
            if isinstance(f, Lyre):
                f.lookAt([3, 1, 3])
            elif isinstance(f, LightString):
                light_strings.append(f)
            elif isinstance(f, Cracra):
                cracras.append(f)
            elif isinstance(f, Z1020):
                smoke.append(f)
            elif isinstance(f, Par2Brod):
                par.append(f)
            elif isinstance(f, LightCubeLZR):
                pass
                #f.color = np.array(colors)*.01
                #f.attrib["laser"] = .99
                #f.attrib["auto_rotation"] = .51
        self.master_effect.update(self.ctrl, cracras, smoke)
        color = self.current_pattern.render(light_strings, af, self.ctrl)
        self.brod_par_effect.update(self.ctrl, par, color)
        self.draw_leds(af)

    def exit(self):
        if self.ctrl.usable:
            self.ctrl.save_settings()
