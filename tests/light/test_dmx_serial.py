"""Detection and framing for the Open DMX USB (FT232) cable.

The cable is a bare FTDI FT232R wired to an RS-485 driver, so the DMX512
frame has to be generated here rather than by fixture firmware.
"""

import time

import pytest

from light import dmx_serial


class FakePort:
    """Stands in for serial.tools.list_ports.ListPortInfo."""

    def __init__(self, device, vid=None, pid=None, serial_number=None):
        self.device = device
        self.vid = vid
        self.pid = pid
        self.serial_number = serial_number


FT232 = FakePort("/dev/ttyUSB0", vid=0x0403, pid=0x6001, serial_number="A50285BI")
ARDUINO = FakePort("/dev/ttyACM0", vid=0x2341, pid=0x0043)
NO_IDS = FakePort("/dev/ttyS0")


@pytest.fixture(autouse=True)
def _no_env_override(monkeypatch):
    monkeypatch.delenv(dmx_serial.PORT_ENV_VAR, raising=False)


def patch_ports(monkeypatch, ports):
    monkeypatch.setattr(dmx_serial, "comports", lambda: ports)


# ---------------------------------------------------------------------------
# detection
# ---------------------------------------------------------------------------


def test_finds_the_ft232_cable(monkeypatch):
    patch_ports(monkeypatch, [ARDUINO, FT232])
    assert dmx_serial.find_open_dmx_port() == "/dev/ttyUSB0"


def test_returns_none_when_no_ft232_is_plugged_in(monkeypatch):
    patch_ports(monkeypatch, [ARDUINO, NO_IDS])
    assert dmx_serial.find_open_dmx_port() is None


def test_returns_none_when_nothing_is_plugged_in(monkeypatch):
    patch_ports(monkeypatch, [])
    assert dmx_serial.find_open_dmx_port() is None


def test_ports_without_usb_ids_do_not_crash_detection(monkeypatch):
    patch_ports(monkeypatch, [NO_IDS])
    assert dmx_serial.find_open_dmx_port() is None


def test_env_var_overrides_autodetection(monkeypatch):
    monkeypatch.setenv(dmx_serial.PORT_ENV_VAR, "/dev/ttyUSB7")
    patch_ports(monkeypatch, [FT232])
    assert dmx_serial.find_open_dmx_port() == "/dev/ttyUSB7"


def test_env_var_wins_even_when_no_cable_is_detected(monkeypatch):
    monkeypatch.setenv(dmx_serial.PORT_ENV_VAR, "/dev/ttyUSB7")
    patch_ports(monkeypatch, [])
    assert dmx_serial.find_open_dmx_port() == "/dev/ttyUSB7"


# ---------------------------------------------------------------------------
# framing
# ---------------------------------------------------------------------------


class FakeSerial:
    """Records the ordered sequence of operations a DMX frame performs."""

    def __init__(self, *args, **kwargs):
        self.init_args = (args, kwargs)
        self.ops = []
        self.closed = False
        self._break = False

    @property
    def break_condition(self):
        return self._break

    @break_condition.setter
    def break_condition(self, value):
        self._break = value
        self.ops.append(("break", value))

    def write(self, data):
        self.ops.append(("write", bytes(data)))

    def flush(self):
        self.ops.append(("flush",))

    def close(self):
        self.closed = True

    def writes(self):
        return [data for op, *rest in self.ops if op == "write" for data in rest]


def test_frame_asserts_break_before_writing_data():
    ser = FakeSerial()
    dmx_serial.send_frame(ser, bytes(512))
    kinds = [op[0] for op in ser.ops]
    assert kinds == ["break", "break", "write", "flush"]
    assert ser.ops[0] == ("break", True)
    assert ser.ops[1] == ("break", False)


def test_frame_is_a_zero_start_code_followed_by_512_channels():
    ser = FakeSerial()
    dmx_serial.send_frame(ser, bytes([7]) + bytes(511))
    (written,) = ser.writes()
    assert len(written) == 513
    assert written[0] == 0x00
    assert written[1] == 7


# ---------------------------------------------------------------------------
# the output thread
# ---------------------------------------------------------------------------


def make_thread(**kwargs):
    return dmx_serial.OpenDmxThread("/dev/null", serial_factory=FakeSerial, **kwargs)


def test_opens_the_port_at_the_dmx512_line_rate():
    thread = make_thread()
    _, kwargs = thread.serial.init_args
    assert kwargs["baudrate"] == 250000
    assert kwargs["bytesize"] == 8
    assert kwargs["parity"] == "N"
    assert kwargs["stopbits"] == 2


def test_short_buffers_are_padded_to_a_full_universe():
    thread = make_thread()
    thread.set_frame(bytes([1, 2, 3]))
    assert thread.snapshot() == bytes([1, 2, 3]) + bytes(509)


def test_oversized_buffers_are_truncated_to_a_full_universe():
    thread = make_thread()
    thread.set_frame(bytes([9]) * 600)
    assert thread.snapshot() == bytes([9]) * 512


def test_caller_can_reuse_its_buffer_without_corrupting_the_frame():
    thread = make_thread()
    caller_buffer = bytearray(512)
    caller_buffer[0] = 255
    thread.set_frame(caller_buffer)
    caller_buffer[0] = 0
    assert thread.snapshot()[0] == 255


def test_stopping_blacks_out_the_rig_and_closes_the_port():
    thread = make_thread()
    thread.set_frame(bytes([255]) * 512)
    thread.start()
    thread.stop()
    assert thread.serial.writes()[-1] == bytes(513)
    assert thread.serial.closed
    assert not thread.is_alive()


def test_the_running_thread_keeps_resending_the_current_frame():
    thread = make_thread()
    thread.set_frame(bytes([42]) + bytes(511))
    thread.start()
    try:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if len(thread.serial.writes()) >= 3:
                break
            time.sleep(0.01)
    finally:
        thread.stop()
    resent = thread.serial.writes()[:3]
    assert len(resent) == 3
    assert all(frame == bytes([0x00, 42]) + bytes(511) for frame in resent)
