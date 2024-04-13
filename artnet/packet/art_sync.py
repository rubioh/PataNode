from bytechomp import dataclass, Parser
from bytechomp.datatypes.declarations import U8
from typing import Self

from artnet.packet.base import ArtOp, ArtBase


@dataclass(frozen=True)
class ArtSyncPayload:
    aux1: U8 = U8(0)
    aux2: U8 = U8(0)


class ArtSync(ArtBase[ArtSyncPayload]):
    _parser = Parser[ArtSyncPayload]().build()
    op_code = ArtOp.SYNC

    @classmethod
    def new(cls) -> Self:
        return cls(payload=ArtSyncPayload())
