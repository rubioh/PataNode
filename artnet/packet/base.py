from typing import Dict, Callable, TypeVar, Generic, Tuple, Self

from bytechomp import Parser, serialize
from bytechomp.datatypes import U16

from artnet.packet.header import ArtOp, ArtHeader, ArtHeaderProtVer, ArtParseError


ARTNET_PORT = 6454
ArtPayload = TypeVar("ArtPayload")
ArtPayloadExt = TypeVar("ArtPayloadExt")


class ArtBase(Generic[ArtPayload]):
    payload: ArtPayload
    extra: bytes

    def __init__(self, payload: ArtPayload, extra: bytes = b""):
        self.payload = payload
        self.extra = extra

    @staticmethod
    def validate(data: ArtPayload, extra) -> None:
        pass

    op_code: ArtOp
    _parser: Parser[ArtPayload]
    __protocol_version_parser = Parser[ArtHeaderProtVer]().build()

    def serialize(self) -> bytes:
        return (
            serialize(ArtHeader(op_code=U16(self.op_code.value)))  # type: ignore
            + self.serialize_protocol_version()
            + serialize(self.payload)  # type: ignore
            + self.extra
        )

    def serialize_protocol_version(self) -> bytes:
        return serialize(ArtHeaderProtVer())  # type: ignore

    @classmethod
    def parse_protocol_version(cls, packet: bytes) -> Tuple[ArtHeaderProtVer | None, bytes]:
        prot_ver, payload = cls.__protocol_version_parser.parse(packet)

        if prot_ver is None:
            raise ArtParseError(f"packet is too short to parse protocol version: len={len(packet)}")

        return prot_ver, payload

    @classmethod
    def parse(cls, packet: bytes) -> Self:
        _, packet = cls.parse_protocol_version(packet)
        data, extra = cls._parser.parse(packet)

        if data is None:
            raise ArtParseError("packet is too short for the expected ArtNet payload")

        cls.validate(data, extra)
        return cls(data, extra)

    @classmethod
    def add_handler(cls, handlers: Dict[ArtOp, Callable[[bytes], "ArtBase"]]) -> None:
        handlers[cls.op_code] = cls.parse

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(payload={self.payload}, extra_len={len(self.extra)})"


class ArtExtBase(Generic[ArtPayload, ArtPayloadExt], ArtBase[ArtPayload]):
    payload_ext: ArtPayloadExt
    payload_ext_extra: bytes

    _extension_parser: Parser[ArtPayloadExt]

    @property
    def extra(self) -> bytes:
        return serialize(self.payload_ext) + self.payload_ext_extra  # type: ignore

    @extra.setter
    def extra(self, data: bytes) -> None:
        min_len = self._extension_parser.min_data_size
        pad_len = min_len - len(data) if len(data) < min_len else 0
        padded = data + bytes([0 for _ in range(pad_len)])
        payload_ext, self.payload_ext_extra = self._extension_parser.parse(padded)
        assert payload_ext is not None
        self.payload_ext = payload_ext

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__}(payload={self.payload}"
            f", payload_ext={self.payload}, payload_ext_extra={self.payload_ext_extra!r})"
        )
