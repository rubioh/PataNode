"""Open DMX USB (FTDI FT232) output.

The cable is a bare FT232 wired straight to an RS-485 driver -- unlike an
Enttec DMX USB PRO there is no firmware doing the timing, so the DMX512
frame is generated here: 250000 baud 8N2, BREAK, mark-after-break, a 0x00
start code, then the 512 channel bytes, repeated continuously.

Sending is done from OpenDmxThread rather than inline: one frame costs about
27 ms on the wire, which would otherwise pin the render loop to ~34 fps.
"""

import os
import threading
import time

import serial
from serial.tools.list_ports import comports

# Stock FT232R ids. Generic enough that other serial adapters share them,
# hence PORT_ENV_VAR for when the guess is wrong.
FTDI_VID = 0x0403
FT232_PID = 0x6001

PORT_ENV_VAR = "PATANODE_DMX_PORT"

UNIVERSE_SIZE = 512
DMX_BAUDRATE = 250000

# Spec minimums are 88 us and 8 us; a little margin costs nothing since the
# frame itself dominates, and the kernel cannot hit those exactly anyway.
BREAK_S = 200e-6
MAB_S = 20e-6

# DMX512 forbids sending faster than 44 packets per second.
MIN_FRAME_PERIOD_S = 1.0 / 44


def find_open_dmx_port() -> str | None:
    """Path of the Open DMX cable, or None if no candidate is plugged in."""
    override = os.environ.get(PORT_ENV_VAR)
    if override:
        return override

    for port in comports():
        if port.vid == FTDI_VID and port.pid == FT232_PID:
            return port.device

    return None


def send_frame(ser, channels: bytes) -> None:
    """Write one DMX512 packet: BREAK, MAB, start code, channel data."""
    ser.break_condition = True
    time.sleep(BREAK_S)
    ser.break_condition = False
    time.sleep(MAB_S)
    ser.write(b"\x00" + channels)
    ser.flush()  # tcdrain: empty the UART before the next break


class OpenDmxThread(threading.Thread):
    """Holds a universe and resends it to the cable until stopped."""

    def __init__(self, port: str, serial_factory=serial.Serial):
        super().__init__(daemon=True, name="open-dmx")
        self.port = port
        self.serial = serial_factory(
            port,
            baudrate=DMX_BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_TWO,
            timeout=0,
        )
        self._frame = bytearray(UNIVERSE_SIZE)
        self._lock = threading.Lock()
        self._stopping = threading.Event()

    def set_frame(self, channels) -> None:
        """Replace the universe. Padded or truncated to 512 channels."""
        frame = bytearray(UNIVERSE_SIZE)
        frame[: min(len(channels), UNIVERSE_SIZE)] = channels[:UNIVERSE_SIZE]
        with self._lock:
            self._frame = frame

    def snapshot(self) -> bytes:
        with self._lock:
            return bytes(self._frame)

    def run(self) -> None:
        while not self._stopping.is_set():
            started = time.monotonic()
            send_frame(self.serial, self.snapshot())
            elapsed = time.monotonic() - started
            self._stopping.wait(max(0.0, MIN_FRAME_PERIOD_S - elapsed))

        send_frame(self.serial, bytes(UNIVERSE_SIZE))
        self.serial.close()

    def stop(self) -> None:
        self._stopping.set()
        if self.ident is None:
            self.serial.close()
            return
        self.join(timeout=2.0)
