from bytechomp import dataclass, Parser
from bytechomp.datatypes.declarations import U8
from enum import IntEnum, IntFlag, auto
from typing import Self

from artnet.packet.base import ArtOp, ArtExtBase


class ArtDiagnosticsPriority(IntEnum):
    LOW = 0x10
    MEDIUM = 0x40
    HIGH = 0x80
    CRITICAL = 0xE0
    # Messages of this type are displayed on a single line in the DMX-Workshop
    # diagnostics display. All other types are displayed in a list box
    VOLATILE = 0xF0


class ArtPollFlags(IntFlag):
    _DEPRECATED = auto()

    # Send ArtPollReply whenever Node conditions change. This selection allows
    # the Controller to be informed of changes without the need to continuously poll.
    REPLY_ON_CHANGE = auto()
    SEND_DIAGNOSTICS = auto()
    UNICAST_DIAGNOSTICS = auto()
    ENABLE_VLC = auto()
    ENABLE_TARGET_MODE = auto()
    _UNUSED = auto()
    _UNUSED2 = auto()


ART_POLL_DEFAULT_FLAGS = ArtPollFlags.REPLY_ON_CHANGE | ArtPollFlags.UNICAST_DIAGNOSTICS


@dataclass(frozen=True)
class ArtPollPayload:
    # set beahviour of node (ArtPollFlags)
    flags: U8
    # the lowest priority of diagnostics message that should be sent
    diag_priority: U8 = U8(ArtDiagnosticsPriority.LOW.value)


@dataclass(frozen=True)
class ArtPollPayloadExt:
    target_port_addr_top_hi: U8 = U8(0)
    target_port_addr_top_lo: U8 = U8(0)
    target_port_addr_bot_hi: U8 = U8(0)
    target_port_addr_bot_lo: U8 = U8(0)
    # The ESTA Manufacturer Code is assigned by ESTA and uniquely identifies
    # the manufacturer that generated this packet.
    # 7FF0 is reserved for experimental products
    esta_man_hi: U8 = U8(0x7F)
    esta_man_lo: U8 = U8(0xF0)
    # The Oem code uniquely identifies the product sending this packet.
    oem_hi: U8 = U8(0)
    oem_lo: U8 = U8(0)


class ArtPoll(ArtExtBase[ArtPollPayload, ArtPollPayloadExt]):
    _parser = Parser[ArtPollPayload]().build()
    _extension_parser = Parser[ArtPollPayloadExt]().build()
    op_code = ArtOp.POLL

    @classmethod
    def new(cls, flags: ArtPollFlags = ART_POLL_DEFAULT_FLAGS) -> Self:
        return cls(payload=ArtPollPayload(U8(flags.value)))
