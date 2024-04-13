#!/usr/bin/env python3.11

import rtmidi
import time

m = rtmidi.MidiOut()
print(m.get_ports())
for i, p in enumerate(m.get_ports()):
    print(f"opening output port {p}")
    m = rtmidi.MidiOut()
    output = m.open_port(i)
    output.send_message([1])

    print(output)
    print(dir(output))
    print("==========")

m = rtmidi.MidiIn()

for i, p in enumerate(m.get_ports()):
    print(f"listening on port {p}")
    m = rtmidi.MidiIn()
    input = m.open_port(i)

    def print_info_for_port(port):
        return lambda t, _: print(f"{port}: {t}")

    input.set_callback(print_info_for_port(p), None)


while True:
    time.sleep(1000)
