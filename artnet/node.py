import socket
import time
from dataclasses import dataclass, field
from time import monotonic
from typing import Self, Dict, Set, Callable
from artnet.packet import (
    artnet_parse_packet,
    ArtBase,
    ArtDmx,
    ArtPoll,
    ArtPollReply,
    ArtParseError,
    ArtSync,
)
from artnet.packet import ARTNET_PORT
from artnet.definitions import IPv4Address, PortAddr


@dataclass
class ArtNetNode:
    ip: str
    __socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    __last_discovery: float = 0.0

    __nodes: Dict[IPv4Address, Set[PortAddr]] = field(default_factory=dict)
    __sequence: int = 0
    __dmx_cb: None | Callable[[bytes], None] = None
    __last_pps: int | None = None
    __packets_since_last_pps = 0
    __last_pps_ts = monotonic()

    def __enter__(self) -> Self:
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.__socket.bind((self.ip, ARTNET_PORT))
        self.__socket.settimeout(0.1)
        # self.__socket.setblocking(False)
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback) -> None:
        self.__socket.close()

    def set_cb(self, cb: Callable[[bytes], None]) -> None:
        self.__dmx_cb = cb

    def tick(self) -> None:
        self._handle_packets()

    def _handle_packets(self) -> None:
        while True:
            if monotonic() > self.__last_pps_ts + 1:
                if self.__packets_since_last_pps or self.__last_pps != 0:
                    self.__last_pps = self.__packets_since_last_pps
                    print(f"pps: {self.__packets_since_last_pps}")
                    self.__packets_since_last_pps = 0
                    self.__last_pps_ts = monotonic()
            try:
                packet, addr = self.__socket.recvfrom(4096)
                art = artnet_parse_packet(packet)
                self.__packets_since_last_pps += 1
                if isinstance(art, ArtPoll):
                    # For now we send just a dumb packet to allow firewall traversals
                    reply = ArtPollReply.new(b"\0\0\0\0", 0, 0)  # TODO
                    self.__socket.sendto(reply.serialize(), (addr[0], ARTNET_PORT))
                elif isinstance(art, ArtDmx):
                    if art.payload.sub_uni == 0 and art.payload.net == 0:
                        # XXX allow other portaddr
                        self.__sequence = art.payload.sequence
                        if self.__dmx_cb:
                            self.__dmx_cb(art.extra)

                elif isinstance(art, ArtSync):
                    ...
                    # TODO: Wait for artsync to trigger callback
                elif any(isinstance(art, ignore) for ignore in (ArtPollReply,)):
                    pass
                else:
                    print("artnet: unhandled ", art, addr)
            except ArtParseError as e:
                print(e)
                print(packet)
            except NotImplementedError as e:
                print(e)
            except (BlockingIOError, OSError):  # XXX
                break

    def __send(self, ip: IPv4Address, pack: ArtBase) -> None:
        try:
            self.__socket.sendto(pack.serialize(), (ip, ARTNET_PORT))
        except (OSError, BlockingIOError) as e:  # XXX
            print("could not send ", pack)
            print(e)
            pass


if __name__ == "__main__":
    import usb.core
    import usb.util

    print("trying to open device with VID = 0x0000 & PID = 0x0001")
    dev = usb.core.find(idVendor=0x0000, idProduct=0x0001)
    if dev is None:
        raise ValueError("Device not found")

    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]

    outep = usb.util.find_descriptor(
        intf,
        # match the first OUT endpoint
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
        == usb.util.ENDPOINT_OUT,
    )

    assert outep is not None

    print("listening for artnet packets on 0.0.0.0")
    with ArtNetNode("0.0.0.0") as node:
        node.set_cb(outep.write)
        while True:
            node.tick()
            time.sleep(1 / 60)
