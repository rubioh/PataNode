from typing import Callable, Dict

from bytechomp import Parser

from artnet.packet.art_dmx import ArtDmx
from artnet.packet.art_poll import ArtPoll
from artnet.packet.art_poll_reply import ArtPollReply, PortType
from artnet.packet.art_sync import ArtSync
from artnet.packet.base import ArtOp, ArtBase, ArtParseError, ArtHeader, ARTNET_PORT


__art_op_handlers: Dict[ArtOp, Callable[[bytes], ArtBase]] = {}
__art_header_parser = Parser[ArtHeader]().build()

ArtPoll.add_handler(__art_op_handlers)
ArtPollReply.add_handler(__art_op_handlers)
ArtDmx.add_handler(__art_op_handlers)
ArtSync.add_handler(__art_op_handlers)


def artnet_parse_packet(packet: bytes) -> ArtBase:
    """
    Raises NotImplementedError or ArtParseError
    """
    header, payload = __art_header_parser.parse(packet)

    if header is None:
        raise ArtParseError(
            f"packet is too short to be an ArtNet packet: len={len(packet)}"
        )
    elif ArtOp(header.op_code) not in __art_op_handlers:
        raise NotImplementedError(
            f"no handler registered for ArtNet op {ArtOp(header.op_code).name}"
        )

    return __art_op_handlers[ArtOp(header.op_code)](payload)


__all__ = [
    "ARTNET_PORT",
    "ArtDmx",
    "ArtParseError",
    "ArtPoll",
    "ArtPollReply",
    "ArtSync",
    "PortType",
    "artnet_parse_packet",
]


if __name__ == "__main__":
    """
    Tiny test suite
    """
    # test deserialization
    hdr = b"Art-Net\0\x00\x50\0\x0e"
    not_implemented_packet = b"Art-Net\0\x00\x51\0\x0e"  # unhandled opcode
    fail_packets = [
        hdr + b"\x00\x00\x00",  # payload too short
        hdr + b"\x00\x00\x00\x00\x00\x00",  # length out of range
        hdr + b"\x00\x00\x00\x00\x03\x00",  # length out of range
        hdr + b"\x00\x00\x00\x00\x02\x00",  # missing extra bytes
    ]
    success_packets = [
        hdr + b"\x00\x00\x00\x00\x00\x02XD",  # missing extra bytes
        hdr
        + b"\x00\x00\x00\x00\x02\x00"
        + b"dmx_data" * (512 // 8),  # missing extra bytes
    ]

    try:
        artnet_parse_packet(not_implemented_packet)
    except NotImplementedError:
        pass

    for i, packet in enumerate(fail_packets):
        try:
            artnet_parse_packet(packet)
        except ArtParseError as e:
            print(e)
        else:
            raise Exception(f"expected packet {i} to throw")

    for packet in success_packets:
        print(artnet_parse_packet(packet))

    # Test serialization
    print(ArtDmx.new(b"XD", 1, 0, 0, 0).serialize())

    data = bytes([i for i in range(256)] * 2)

    print(ArtDmx.new(data, 1, 0, 0, 0).serialize())
    print(ArtPoll.new())
    print(ArtPoll.new().serialize())
