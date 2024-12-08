import socket
import threading
import time

import ifaddr

from dataclasses import dataclass, field
from math import sin
from queue import Queue
from time import monotonic
from typing import Self, Tuple, Dict, List, Set

from artnet.definitions import Universe, IPv4Address, PortAddr, ARTNET_POLL_INTERVAL_S
from artnet.net_util import get_broadcast_address, parse_ip
from artnet.packet import (
    ARTNET_PORT,
    ArtBase,
    ArtDmx,
    ArtParseError,
    ArtPoll,
    ArtPollReply,
    ArtSync,
    PortType,
    artnet_parse_packet,
)
from util import assert_never


@dataclass
class ArtNetController:
    __sockets: list[socket.socket] = field(default_factory=list)
    __last_discovery: float = 0.0
    __ips: list[Tuple[IPv4Address, int]] = field(default_factory=list)

    __nodes: Dict[IPv4Address, Set[PortAddr]] = field(default_factory=dict)
    __sequence: int = 1

    def __enter__(self) -> Self:
        self.__ips = [
            (IPv4Address(ip.ip), ip.network_prefix)
            for adapter in ifaddr.get_adapters()
            for ip in adapter.ips
            if isinstance(ip.ip, str) and not ip.ip.startswith("169.254")
        ]

        for i in range(len(self.__ips)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind((str(self.__ips[i][0]), ARTNET_PORT))
            sock.setblocking(False)
            self.__sockets += [sock]

        self.__nodes = {
            IPv4Address("10.2.0.2"): set([PortAddr(0)]),
            IPv4Address("10.2.0.3"): set([PortAddr(0)]),
        }

        return self

    def __exit__(self, exception_type, exception_value, exception_traceback) -> None:
        for sock in self.__sockets:
            sock.close()

    def tick(self) -> None:
        self.__maybe_discover()
        self.__maybe_handle_packets()
#       self.__maybe_disconnect_nodes() #TODO

    def __maybe_discover(self) -> None:
        if monotonic() > self.__last_discovery + ARTNET_POLL_INTERVAL_S:
            for i, sock in enumerate(self.__sockets):
                try:
                    sock.sendto(
                        ArtPoll.new().serialize(),
                        (str(get_broadcast_address(*self.__ips[i])), ARTNET_PORT),
                    )
                except (BlockingIOError, OSError):  # XXX
                    pass

            self.__last_discovery = monotonic()

    def __maybe_handle_packets(self) -> None:
        for i, sock in enumerate([*self.__sockets]):
            try:
                while True:
                    packet, addr = sock.recvfrom(4096)
                    art = artnet_parse_packet(packet)

                    if isinstance(art, ArtPollReply):
                        self.__handle_art_poll_reply(art, addr[0])
                    elif any(isinstance(art, ignore) for ignore in (ArtDmx, ArtPoll, ArtSync)):
                        # TODO: The Controller that broadcasts an ArtPoll should also reply to its own message (by unicast) with an ArtPollReply
                        pass
                    else:
                        print("artnet: unhandled ", art, addr)
            except ArtParseError as e:
                print(e)
                print(packet)
            except NotImplementedError as e:
                print(e)
            except (BlockingIOError, OSError):  # XXX
                continue

    def __handle_art_poll_reply(self, reply: ArtPollReply, ip: str) -> None:
        return  # XXX
        # check ip == reply.ip_address
        port_addr_base = (reply.payload.net_switch & 0x7F) << 8 | (
            (reply.payload.sub_switch & 0xF) << 4
        )

        for i, uni_type in enumerate(reply.payload.port_types):
            parsed_type = PortType.parse(uni_type)

            if parsed_type.can_output:
                if ip not in self.__nodes:
                    self.__nodes[ip] = set[int]()

                self.__nodes[ip].add(port_addr_base | reply.payload.sw_out[i])

    def __get_sock_by_ip(self, ip: IPv4Address) -> socket.socket | None:
        ip1 = sum([byte << (8 * i) for i, byte in enumerate(parse_ip(ip)[::-1])])

        for i, (test_ip, prefix) in enumerate(self.__ips):
            ip2 = sum(
                (byte << (8 * i) for i, byte in enumerate(parse_ip(test_ip)[::-1]))
            )
            mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF

            if ip1 & mask == ip2 & mask:
                return self.__sockets[i]

        return None

    def __send(self, ip: IPv4Address, pack: ArtBase) -> None:
        sock = self.__get_sock_by_ip(ip)
#       assert sock, f"no socket found for ip: {ip}"

        if sock is None:
#           print(f"artnet: no socket found for ip {ip}")
            return
        try:
            sock.sendto(pack.serialize(), (str(ip), ARTNET_PORT))
        except (OSError, BlockingIOError):  # XXX
#           print("could not send ", pack)
#           print(e)
            pass

    def get_all_universes(self) -> List[Universe]:
        ret = list[Universe]()

        for ip, port_addrs in self.__nodes.items():
            for port_addr in port_addrs:
                ret.append(Universe(ip, port_addr))

        return ret

    def _set_universe(self, universe: Universe, data: bytes, physical: int = 0) -> None:
        net = (universe.port_addr & 0x7F00) >> 8
        sub_uni = universe.port_addr & 0xFF
        self.__send(
            universe.ip,
            ArtDmx.new(
                data=data,
                net=net,
                sub_uni=sub_uni,
                physical=physical,
                sequence=self.__sequence,
            ),
        )

    def sync_universes(self) -> None:
        for ip, subnet_prefix in self.__ips:
            self.__send(get_broadcast_address(ip, subnet_prefix), ArtSync.new())

        self.__sequence += 1

    def set_all_universes(self, data: bytes, offsets: Dict[Universe, int] = {}) -> None:
        padding = max(offsets.values()) if offsets else 0
        data_with_padding = data + bytes([0] * padding)

        for universe in self.get_all_universes():
            start = offsets.get(universe, 0)
            end = start + len(data)
            self._set_universe(universe, data_with_padding[start:end])

        self.sync_universes()

    def set_universe(self, data: bytes, universe: Universe, offsets: Dict[Universe, int] = {}) -> None:
        padding = max(offsets.values()) if offsets else 0
        data_with_padding = data + bytes([0] * padding)
        start = offsets.get(universe, 0)
        end = start + len(data)
        self._set_universe(universe, data_with_padding[start:end])


class ArtNetControllerThread(threading.Thread):
    def __init__(self):
        self.__queue = Queue[None | Tuple[bytes, Dict[Universe, int]] | bool]()
        super().__init__(daemon=True)

    def run(self):
        with ArtNetController() as ctrl:
            black = bytes([0] * 512)
            ctrl.set_all_universes(black)

            while True:
                ctrl.tick()
                msg = self.__queue.get()

                if msg is None:
                    break
                elif isinstance(msg, tuple):
                    ctrl.set_universe(msg[0], msg[1])
                elif isinstance(msg, bool):
                    ctrl.sync_universes()
                else:
                    assert_never(msg)

    def exit(self):
        self.__queue.put(None)

    def show(self, buffer: bytes, univ: Universe) -> None:
        self.__queue.put((buffer, univ))

    def sync(self) -> None:
        self.__queue.put(
            True
        )  # FIXME Lazy bitch should do proper messages instead of this bs


if __name__ == "__main__":
#   from light.light import nouveau_casino_offsets

    artnet_ctrl = ArtNetControllerThread()
    artnet_ctrl.start()

    while True:
        red = bytes([int((sin(monotonic()) + 1) / 2 * 255), 0, 0] * 170 + [0, 0])
#       artnet_ctrl.show(red, nouveau_casino_offsets)
        time.sleep(1 / 60)
