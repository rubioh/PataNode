import os
import pickle

import pygame as pg
import pygame.midi


def print_device_info():
    for i in range(pygame.midi.get_count()):
        r = pygame.midi.get_device_info(i)
        interf, name, input, output, opened = r

        in_out = ""

        if input:
            in_out = "(input)"

        if output:
            in_out = "(output)"

        print(
            "%2i: interface :%s:, name :%s:, opened :%s:  %s"
            % (i, interf, name, opened, in_out)
        )


class MidiController:
    def __init__(self, device_id=-1):
        pygame.midi.init()
        pygame.fastevent.init()
        print_device_info()
        self.init_params()
        self.device_id = device_id

        try:
            self.device = pygame.midi.Input(device_id)
        except Exception:
            pass

    def check_events(self):
        if self.device.device_id == -1:
            return

        if self.device.poll():
            midi_events = self.device.read(10)
            midi_evs = pygame.midi.midis2events(midi_events, self.device.device_id)

            for m_e in midi_evs:
                pg.fastevent.post(m_e)

    def init_params(self):
        self.bank = 0

        self.id_to_keys_pot = {14 + i: "P" + str(i) for i in range(9)}
        self.potentiometre = [{"P" + str(i): 0 for i in range(9)} for i in range(4)]

        self.id_to_keys_sliders = {3 + i: "S" + str(i) for i in range(9)}
        self.sliders = [{"S" + str(i): 0 for i in range(9)} for i in range(4)]

        self.id_to_keys_buttons = {23 + i: "S" + str(i) for i in range(9)}

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
        except Exception:
            print("No previous_state")

    def parse(self, event):
        d = event.__dict__
        status = d["status"]
        data1 = d["data1"]
        data2 = d["data2"]

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

        if status == 192:
            if data1 == 0:
                self.precision[self.bank]["molette"] = data2

        if status == 79:
            self.bank = data1

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
        self.save_settings()
        pygame.midi.quit()
