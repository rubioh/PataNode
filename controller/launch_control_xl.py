import rtmidi

from controller.qt_controller import SimpleMidiReceiver, get_port_by_name
from typing import Callable, NewType
from enum import IntEnum, IntFlag, Enum, auto


class LEDColor(IntEnum):
    BLACK = 0
    RED_LO = 0b01
    RED_MI = 0b10
    RED_HI = 0b11
    GREEN_LO = 0b01 << 4
    GREEN_MI = 0b10 << 4
    GREEN_HI = 0b11 << 4
    AMBER_LO = RED_LO | GREEN_LO
    AMBER_MI = RED_MI | GREEN_MI
    AMBER_HI = RED_HI | GREEN_HI
    YELLOW_HI = GREEN_HI | RED_MI
    YELLOW_MI = GREEN_MI | RED_LO
    ORANGE_HI = GREEN_MI | RED_HI
    ORANGE_MI = GREEN_LO | RED_MI
    DEEP_ORANGE = GREEN_LO | RED_HI
    LIGHT_GREEN = GREEN_HI | RED_LO


class LEDFlag(IntFlag):
    CLEAR = 1 << 3
    COPY = 1 << 2


BUTTON_LONG_PRESS_MS = 2500


class ButtonEvent(Enum):
    PRESS = auto()
    LONG = auto()
    RELEASE = auto()


ValueChanged = NewType("ValueChanged", int)
Event = ButtonEvent | ValueChanged


class LaunchControlMidiReceiver(SimpleMidiReceiver):
    LED_INDICES = {
        **{f"K{i+0}": i for i in range(8)},
        **{f"K{i+8}": i + 0x8 for i in range(8)},
        **{f"K{i+16}": i + 0x10 for i in range(8)},
        **{f"B{i+0}": i + 0x18 for i in range(8)},
        **{f"B{i+8}": i + 0x20 for i in range(8)},
        "device": 0x28,
        "mute": 0x29,
        "solo": 0x2A,
        "record_arm": 0x2B,
        "up": 0x2C,
        "down": 0x2D,
        "left": 0x2E,
        "right": 0x2F,
    }
    MAX_INDEX = max(LED_INDICES.values())
    MIDI_IN_PORT = "Launch Control XL:Launch Control XL Launch Contro 20:0"
    CC_TO_ID_KNOBS = {i: f"K{i}" for i in range(24)}
    CC_TO_ID_FADERS = {24 + i: "F" + str(i) for i in range(8)}
    CC_TO_ID_BUTTONS = {32 + i: "B" + str(i) for i in range(24)}

    def __init__(self):
        super().__init__()
        midi_out_port = "Launch Control XL:Launch Control XL Launch Contro 20:0"
        self._midi_out = get_port_by_name(midi_out_port, rtmidi.MidiOut())

        if self._midi_out is None:
            self.usable = False
            return

        self.set_template(0)
        self._button_pressed_ts = {}
        self._event_cb = {}

    def set_callback(
        self, uid: str, fun: Callable[[str, Event, int, int], None]
    ) -> None:
        self._event_cb[uid] = fun

    def callback(self, uid: str, event: Event, time_ms: int, dur: int) -> None:
        if uid in self._event_cb:
            self._event_cb[uid](uid, event, time_ms, dur)

    def handle_cc(self, cc, value) -> None:
        uid = self.cc_to_uid.get(cc)

        if uid is None:
            return super().handle_cc(cc, value)

        previous_value = self.value(uid)
        super().handle_cc(cc, value)

        if uid.startswith("B"):
            if not previous_value and value:
                self._button_pressed_ts[uid] = (self._time_ms, False)
                self.callback(uid, ButtonEvent.PRESS, self._time_ms, 0)
                # key press event callback call
            elif previous_value and not value:
                if uid not in self._button_pressed_ts:
                    print(f"ignoring {uid} release")
                    return

                pressed_ts, is_long = self._button_pressed_ts.pop(uid)
                dur = self._time_ms - pressed_ts
                self.callback(uid, ButtonEvent.RELEASE, self._time_ms, dur)
        else:
            # TODO: move smoothed value callback in tick() together with long button pressed
            self.callback(uid, value, self._time_ms, 0)

    def maybe_handle_sysex(self, msg) -> bool:
        if (
            msg[0] == 0xF0
            and msg[1] == 0x00
            and msg[2] == 0x20
            and msg[3] == 0x29
            and msg[4] == 0x02
            and msg[5] == 0x11
            and msg[6] == 0x77
            and msg[8] == 0xF7
        ):
            self.template = msg[7]
            print(f"changed template to n{self.template}")
            return True

        return False

    def set_template(self, template: int) -> None:
        assert template < 16
        self.template = 0
        self._midi_out.send_message(
            [0xF0, 0x00, 0x20, 0x29, 0x02, 0x11, 0x77, template, 0xF7]
        )

    def set_led_raw(self, template: int, index: int, value: int) -> None:
        assert 0x0 <= template <= 0xF
        assert 0x0 <= index <= self.MAX_INDEX
        self._midi_out.send_message(
            [0xF0, 0x00, 0x20, 0x29, 0x02, 0x11, 0x78, template, index, value, 0xF7]
        )

    def set_led(self, index_key: str, color: LEDColor) -> None:
        if not self.usable:
            return

        index = self.LED_INDICES[index_key]
        self.set_led_raw(
            self.template, index, color.value | LEDFlag.CLEAR | LEDFlag.COPY
        )
