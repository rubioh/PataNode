import time
import numpy as np
import libusb_package
import usb.core
import usb.backend.libusb1

libusb1_backend = usb.backend.libusb1.get_backend(
    find_library=libusb_package.find_library
)


class LightDevice:
    def __init__(self, verbose=False):
        self.USB_VID = 0xCAFE
        self.outep = []
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

    def init_usb_device(self):
        self.load_pataboite()

    def to_bytes(self, light_buffer):
        flat = np.array(light_buffer)
        flat *= 255
        flat = np.clip(flat, 0, 255).astype("u1")
        return flat.tobytes()

    def write(self, light_buffer):
        byte_array = self.to_bytes(light_buffer)
        for idx, out in zip(range(len(self.outep)), self.outep):
            out.write(byte_array[512 * idx : 512 * (idx + 1)])
        self.prev_ts = time.time()
