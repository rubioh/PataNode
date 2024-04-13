import os
import rtmidi
import sys
import pickle
from PyQt5.QtCore import pyqtSignal, QObject, Qt
import numpy as np


def get_port_by_name(port_name, client):
    for i in range(client.get_port_count()):
        print(client.get_port_name(i))
        if port_name in client.get_port_name(i):
            return client.open_port(i)

    # Report available ports if not found
    msg = f"Unknown port {port_name}"
    for i in range(client.get_port_count()):
        msg += f"\n - {client.get_port_name(i)}"
    print(msg)
    return None


class SimpleMidiReceiver:
    DEFAULT_SETTINGS_FILE = "controller/controller_last_status.pickle"
    MIDI_IN_PORT: str
    CC_TO_ID_KNOBS: dict[int, str]
    CC_TO_ID_FADERS: dict[int, str]
    CC_TO_ID_BUTTONS: dict[int, str]
    uid_values: dict[str, int | None]

    def __init__(self):
        super().__init__()
        self.init_params()
        self.init_controller()

    def init_controller(self):
        self._time_ms = 0

        self._midi_in = get_port_by_name(self.MIDI_IN_PORT, rtmidi.MidiIn())
        if self._midi_in is None:
            self.usable = False
            return

        self._midi_in.ignore_types(sysex=False, timing=False, active_sense=False)
        self._midi_in.set_callback(self._midi_in_callback, self)
        self.usable = True

    @staticmethod
    def _midi_in_callback(msg_time_ms_tup, self: "SimpleMidiReceiver") -> None:
        self._time_ms += int(msg_time_ms_tup[1] * 1000)
        msg = msg_time_ms_tup[0]
        status = msg[0]
        if status == 176:
            self.handle_cc(msg[1], msg[2])
        elif self.maybe_handle_sysex(msg):
            pass
        else:
            print(f"unhandled midi message: {msg}")

    def maybe_handle_sysex(self, msg) -> bool:
        return False

    def get_uid_values(self) -> dict[str, int | None]:
        return self.uid_values

    def bind_to_controller(self, uid="P0", vmin=0, vmax=1, scale="linear"):
        assert uid in self.get_uid_values()
        val = self.get_uid_values()[uid]
        if val is None:
            val = vmin
        if scale == "linear":
            return val / 127 * (vmax - vmin) + vmin
        elif scale == "log":
            step = (np.log(vmax) - np.log(vmin)) / (128)
            return np.exp(np.log(vmin) + val * step)
        elif scale == "sigmoid":
            if val == 0:
                return vmin
            elif val == 127:
                return vmax
            else:
                x = val / 127 * (vmax - vmin)
                return 1 / (1 + np.exp(-(x - 0.5) * 10)) + vmin
        else:
            raise ValueError(f"unknown scale {scale}")

    def init_params(self):
        self.cc_to_uid = {
            k: v
            for d in [self.CC_TO_ID_KNOBS, self.CC_TO_ID_FADERS, self.CC_TO_ID_BUTTONS]
            for k, v in d.items()
        }
        self.uid_values = {uid: 0 for uid in self.cc_to_uid.values()}

        try:
            self.load_settings()
        except:
            print("No previous_state")

    def handle_cc(self, cc, value):
        if cc in self.cc_to_uid:
            self.uid_values[self.cc_to_uid[cc]] = value
        else:
            print(f"unhandled midi cc {cc}, {value}")

    def load_settings(self, file=None):
        filename = file or self.DEFAULT_SETTINGS_FILE
        self.uid_values = pickle.load(open(filename, "rb"))

    def save_settings(self, file=None):
        filename = file or self.DEFAULT_SETTINGS_FILE
        pickle.dump(self.uid_values, open(filename, "wb"))

    def value(self, arg: int | str) -> int | None:
        if isinstance(arg, int):
            return self.uid_values[self.cc_to_uid[arg]]
        elif isinstance(arg, str):
            return self.uid_values[arg]


class MidiReceiver(QObject):
    # Internal signal for handing over MIDI events in thread-safe manner
    _queue_message = pyqtSignal(int, int, int, int)

    """
    Qt signal for a received MIDI message. Signature is:
        int: status
        int: data1
        int: data2
        int: event time in ms
    """
    process_message = pyqtSignal(int, int, int, int)

    def __init__(self, midi_in_port):
        super().__init__()
        self.init_params()
        self.init_controller(midi_in_port)

    def init_controller(self, midi_in_port):
        self._midi_in = get_port_by_name(midi_in_port, rtmidi.MidiIn())
        if self._midi_in is None:
            self.usable = False
            return
        self._midi_in.set_callback(self._midi_in_callback, self)
        self._time_ms = 0
        self._queue_message.connect(
            self._thread_safe_queue_message, Qt.QueuedConnection
        )
        self.usable = True

    def _thread_safe_queue_message(self, status, data1, data2, time):
        self.process_message.emit(status, data1, data2, time)

    @staticmethod
    def _midi_in_callback(msg_time_ms_tup, self):
        self._time_ms += int(msg_time_ms_tup[1] * 1000)
        msg = msg_time_ms_tup[0]
        status = msg[0]
        data1 = msg[1]
        data2 = msg[2]
        self._queue_message.emit(status, data1, data2, self._time_ms)

    def bind_to_controller(self, value="P0", vmin=0, vmax=1, scale="linear", bank=0):
        if "P" in value:
            var = self.potentiometre[bank][value]
        elif "S" in value:
            var = self.sliders[bank][value]
        if scale == "linear":
            var = var / 127 * (vmax - vmin) + vmin
        if scale == "log":
            step = (np.log(vmax) - np.log(vmin)) / (128)
            var = np.exp(np.log(vmin) + var * step)
        return var

    def init_params(self):
        self.bank = 0

        self.id_to_keys_pot = {14 + i: "P" + str(i) for i in range(9)}
        self.potentiometre = [{"P" + str(i): 64 for i in range(9)} for i in range(4)]

        self.id_to_keys_sliders = {3 + i: "S" + str(i) for i in range(9)}
        self.sliders = [{"S" + str(i): 64 for i in range(9)} for i in range(4)]

        self.id_to_keys_buttons = {23 + i: "B" + str(i) for i in range(9)}

        self.buttons = [{"B" + str(i): 0 for i in range(9)} for i in range(4)]

        self.control = {
            "play": 0,
            "stop": 0,
            "next": 0,
            "previous": 0,
            "reset": 0,
            "rec": 0,
        }

        self.precision = [
            {"molette": 0, "slider": 0, "rightB": 0, "leftB": 0} for i in range(4)
        ]
        try:
            self.load_settings()
        except:
            print("No previous_state")

    # Parsing for midi Pocket Control
    def parse_data(self, status, data1, data2):
        if status == 176:
            if data1 in self.id_to_keys_pot.keys():
                key = self.id_to_keys_pot[data1]
                self.potentiometre[self.bank][key] = data2
            if data1 in self.id_to_keys_sliders.keys():
                key = self.id_to_keys_sliders[data1]
                self.sliders[self.bank][key] = data2
            if data1 in self.id_to_keys_buttons.keys():
                key = self.id_to_keys_buttons[data1]
                self.buttons[self.bank][key] = data2

            if data1 == 46:
                self.control["stop"] ^= data2 % 2
            if data1 == 45:
                self.control["play"] ^= data2 % 2
            if data1 == 48:
                self.control["next"] = data2 % 2
            if data1 == 47:
                self.control["previous"] = data2 % 2
            if data1 == 49:
                self.control["reset"] = data2 % 2
            if data1 == 44:
                self.control["rec"] ^= data2 % 2

            if data1 == 60:
                self.precision[self.bank]["slider"] = data2
            if data1 == 64:
                self.precision[self.bank]["rightB"] = data2
            if data1 == 67:
                self.precision[self.bank]["leftB"] = data2

            if data1 == 2 and data2 == 127:
                self.bank += 1
                self.bank %= 4
                print(self.bank)

            if data1 == 1 and data2 == 127:
                self.bank -= 1
                self.bank %= 4
                print(self.bank)

        elif status == 192:
            if data1 == 0:
                self.precision[self.bank]["molette"] = data2

        elif status == 79:
            self.bank = data1
        else:
            print(f"unhandled status {status}, {data1}, {data2}")

    def load_settings(self, name=None, full_path=False):
        if name is None:
            name = "controller_state"
        if full_path:
            state = pickle.load(open(name, "rb"))
        else:
            state = pickle.load(
                open(os.path.join("controller/", str(name) + ".pickle"), "rb")
            )

        if isinstance(state["precision"], dict):  # v.0.0 parsing state
            self.precision[0] = state["precision"]
            self.sliders[0] = state["sliders"]
            self.potentiometre[0] = state["potentiometre"]
        else:  # v.0.1 current version parsing state
            self.precision = state["precision"]
            self.sliders = state["sliders"]
            self.potentiometre = state["potentiometre"]

    def save_settings(self, name=None):
        state = {
            "sliders": self.sliders,
            "potentiometre": self.potentiometre,
            "precision": self.precision,
        }
        if name is None:
            pickle.dump(state, open("controller/controller_state2.pickle", "wb"))
        else:
            pickle.dump(state, open("controller/" + str(name) + ".pickle", "wb"))

    def quit(self):
        sys.exit(0)
