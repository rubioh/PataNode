"""LightDevice picks an output sink: Pataboite first, USB-DMX cable second."""

import pytest

import light.device as device
from light.device import LightDevice


class Args:
    def __init__(self, no_usb=False):
        self.no_usb = no_usb


class FakeDmxThread:
    instances = []

    def __init__(self, port):
        self.port = port
        self.frames = []
        self.started = False
        self.stopped = False
        FakeDmxThread.instances.append(self)

    def start(self):
        self.started = True

    def set_frame(self, frame):
        self.frames.append(bytes(frame))

    def stop(self):
        self.stopped = True


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    FakeDmxThread.instances = []
    monkeypatch.setattr(device, "OpenDmxThread", FakeDmxThread)


def patch_rig(monkeypatch, pataboite=None, dmx_port=None):
    def find(**kw):
        # pyusb returns an iterator for find_all, a single device otherwise
        if kw.get("find_all"):
            return iter([pataboite] if pataboite else [])
        return pataboite

    monkeypatch.setattr(device.usb.core, "find", find)
    monkeypatch.setattr(device, "find_open_dmx_port", lambda: dmx_port)


class FakePataboite:
    """Minimal stand-in for the Pataboite's pyusb device object."""

    def __init__(self):
        self.written = []

    def get_active_configuration(self):
        return {(0, 0): "intf"}


@pytest.fixture
def pataboite(monkeypatch):
    dev = FakePataboite()
    endpoint = type("Endpoint", (), {"write": lambda self, data: None})()
    monkeypatch.setattr(device.usb.util, "find_descriptor", lambda *a, **k: endpoint)
    return dev


def test_connects_to_the_dmx_cable_when_no_pataboite_is_present(monkeypatch):
    patch_rig(monkeypatch, pataboite=None, dmx_port="/dev/ttyUSB0")
    LightDevice(Args())
    (thread,) = FakeDmxThread.instances
    assert thread.port == "/dev/ttyUSB0"
    assert thread.started


def test_pataboite_takes_priority_over_the_dmx_cable(monkeypatch, pataboite):
    patch_rig(monkeypatch, pataboite=pataboite, dmx_port="/dev/ttyUSB0")
    LightDevice(Args())
    assert FakeDmxThread.instances == []


def test_no_usb_flag_skips_all_detection(monkeypatch):
    patch_rig(monkeypatch, pataboite=None, dmx_port="/dev/ttyUSB0")
    LightDevice(Args(no_usb=True))
    assert FakeDmxThread.instances == []


def test_survives_having_no_output_hardware_at_all(monkeypatch):
    patch_rig(monkeypatch, pataboite=None, dmx_port=None)
    dev = LightDevice(Args())
    dev.write([0.0] * 512)  # must not raise
    assert FakeDmxThread.instances == []


def test_a_failing_port_does_not_take_the_app_down(monkeypatch):
    import serial

    def explode(port):
        raise serial.SerialException("port busy")

    patch_rig(monkeypatch, pataboite=None, dmx_port="/dev/ttyUSB0")
    monkeypatch.setattr(device, "OpenDmxThread", explode)
    dev = LightDevice(Args())
    dev.write([0.0] * 512)  # must not raise


def test_write_forwards_the_scaled_universe_to_the_cable(monkeypatch):
    patch_rig(monkeypatch, pataboite=None, dmx_port="/dev/ttyUSB0")
    dev = LightDevice(Args())

    buffer = [0.0] * 512
    buffer[0] = 1.0  # engine works in 0..1, the wire wants 0..255
    buffer[1] = 0.5
    dev.write(buffer)

    (thread,) = FakeDmxThread.instances
    (frame,) = thread.frames
    assert len(frame) == 512
    assert frame[0] == 255
    assert frame[1] == 127


def test_closing_blacks_out_the_cable(monkeypatch):
    patch_rig(monkeypatch, pataboite=None, dmx_port="/dev/ttyUSB0")
    dev = LightDevice(Args())
    dev.close()
    (thread,) = FakeDmxThread.instances
    assert thread.stopped
