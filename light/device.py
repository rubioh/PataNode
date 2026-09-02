import atexit
import time

import libusb_package
import numpy as np
import serial
import usb.backend.libusb1
import usb.core

from light.dmx_serial import OpenDmxThread, find_open_dmx_port

libusb1_backend = usb.backend.libusb1.get_backend(
    find_library=libusb_package.find_library
)


class LightDevice:
    def __init__(self, args, verbose=False):
        self.no_usb = args.no_usb
        self.open_dmx = None
        self.outep = []
        if self.no_usb:
            return
        self.USB_VID = 0xCAFE
        if verbose:
            self.list_usb_devices()
        self.init_usb_device()

    def list_usb_devices(self):
        print("Looking for usb devices : ")
        devices = usb.core.find(find_all=True)
        for device in devices:
            print("\t Found device : ", device)
            print("====" * 20)
            print("====" * 20)
            print("====" * 20)

    def connect(self):
        self.cfg = self.dev.get_active_configuration()
        intf = self.cfg[(0, 0)]

        self.outep.append(
            usb.util.find_descriptor(
                intf,
                custom_match=lambda x: usb.util.endpoint_direction(x.bEndpointAddress)
                == usb.util.ENDPOINT_OUT,
            )
        )
        assert self.outep[0] is not None

    def check_usb_devices(self) -> None:
        for printer in usb.core.find(find_all=True, bDeviceClass=7):
            print(printer)
        devs = usb.core.find(find_all=True)
        for device in devs:
            print(device)
        print(list(usb.core.find(find_all=True, backend=libusb1_backend)))

    def load_pataboite(self):
        self.check_usb_devices()
        self.dev = usb.core.find(idVendor=0x0000, idProduct=0x0001)
        # print("Pataboite detected : \n", self.dev)
        if self.dev is not None:
            self.connect()
            print("Pataboite connected")
        else:
            print("No pataboite gros noob")

    def load_open_dmx(self):
        """Fall back to an Open DMX USB cable when there is no Pataboite."""
        port = find_open_dmx_port()
        if port is None:
            print("No usb-dmx cable either")
            return

        try:
            self.open_dmx = OpenDmxThread(port)
        except serial.SerialException as e:
            # Busy port, missing permissions, or an FT232 that is not a
            # DMX cable at all -- none of it should stop the show.
            print(f"Could not open usb-dmx cable on {port}: {e}")
            return

        self.open_dmx.start()
        atexit.register(self.close)
        print(f"usb-dmx connected on {port}")

    def close(self):
        """Black out and release the cable. Safe to call more than once."""
        if self.open_dmx is None:
            return
        open_dmx, self.open_dmx = self.open_dmx, None
        open_dmx.stop()

    def init_usb_device(self):
        self.load_pataboite()
        if self.dev is None:
            self.load_open_dmx()

    def to_bytes(self, light_buffer):
        flat = np.array(light_buffer)
        flat *= 255
        flat = np.clip(flat, 0, 255).astype("u1")
        return flat.tobytes()

    def write(self, light_buffer):
        if self.no_usb:
            return
        byte_array = self.to_bytes(light_buffer)
        if self.open_dmx is not None:
            self.open_dmx.set_frame(byte_array)
        for idx, out in zip(range(len(self.outep)), self.outep):
            out.write(byte_array[512 * idx : 512 * (idx + 1)])
        self.prev_ts = time.time()
