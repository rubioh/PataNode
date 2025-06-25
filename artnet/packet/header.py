from enum import Enum
from dataclasses import dataclass

from bytechomp import Annotated
from bytechomp.datatypes import U8, U16


class ArtParseError(Exception):
    pass


class ArtOp(Enum):
    """
    This enum is directly derived from the ArtNet specification Table 1
    """

    # No other data is contained in this UDP packet .
    POLL = 0x2000
    # It contains device status information.
    POLLREPLY = 0x2100
    # Diagnostics and data logging packet.
    DIAGDATA = 0x2300
    # It is used to send text based parameter commands.
    COMMAND = 0x2400
    # It is used to request data such as products URLs
    DATAREQUEST = 0x2700
    # It is used to reply to ArtDataRequest packets.
    DATAREPLY = 0x2800
    # It contains zero start code DMX512 information for a single Universe.
    DMX = 0x5000
    OUTPUT = 0x5000
    # It contains non-zero start code (except RDM) DMX512 information for a single Universe.
    NZS = 0x5100
    # It is used to force synchronous transfer of ArtDmx packets to a node’s output.
    SYNC = 0x5200
    # It contains remote programming information for a Node.
    ADDRESS = 0x6000
    # It contains enable – disable data for DMX inputs.
    INPUT = 0x7000
    # It is used to request a Table of Devices (ToD) for RDM discovery.
    TODREQUEST = 0x8000
    # It is used to send a Table of Devices (ToD) for RDM discovery.
    TODDATA = 0x8100
    # It is used to send RDM discovery control messages.
    TODCONTROL = 0x8200
    # It is used to send all non discovery RDM messages.
    RDM = 0x8300
    # It is used to send compressed, RDM Sub-Device data.
    RDMSUB = 0x8400
    # It contains vide o screen setup information for nodes that implement the extended video features.
    VIDEOSETUP = 0xA010
    # It contains colour palette setup information for nodes that implement the extended video features.
    VIDEOPALETTE = 0xA020
    # It contains display data for nodes that implement the extended video features.
    VIDEODATA = 0xA040
    # This packet is deprecated.
    MACMASTER = 0xF000
    # This packet is deprecated.
    MACSLAVE = 0xF100
    # It is used to upload new firmware or firmware extensions to the Node.
    FIRMWAREMASTER = 0xF200
    # It is returned by the node to acknowledge receipt of an ArtFirmwareMaster packet or ArtFileTnMaster packet.
    FIRMWAREREPLY = 0xF300
    # Uploads user file to node.
    FILETNMASTER = 0xF400
    # Downloads user file from node.
    FILEFNMASTER = 0xF500
    # Server to Node acknowledge for download packets.
    FILEFNREPLY = 0xF600
    # It is used to re- programme the IP address and Mask of the Node.
    IPPROG = 0xF800
    # It is returned by the node to acknowledge receipt of an ArtIpProg packet .
    IPPROGREPLY = 0xF900
    # It is Unicast by a Media Server and acted upon by a Controller.
    MEDIA = 0x9000
    # It is Unicast by a Controller and acted upon by a Media Server.
    MEDIAPATCH = 0x9100
    # It is Unicast by a Controller and acted upon by a Media Server.
    MEDIACONTROL = 0x9200
    # It is Unicast by a Media Server and acted upon by a Controller.
    MEDIACONTRLREPLY = 0x9300
    # It is used to transport time code over the network.
    TIMECODE = 0x9700
    # Used to synchronise real time date and clock
    TIMESYNC = 0x9800
    # Used to send trigger macros
    TRIGGER = 0x9900
    # Requests a node's file list
    DIRECTORY = 0x9A00
    # Replies to OpDirectory with file list
    DIRECTORYREPLY = 0x9B00


@dataclass(frozen=True)
class ArtHeader:
    # Magic ArtNet string. Must always be "Art-Net\0"
    _id: Annotated[bytes, 8] = b"Art-Net\0"

    # TODO: ensure correct byte order in serializatin (little endian)
    # Packet type
    op_code: U16 = U16(ArtOp.POLL.value)

    def __post_init__(self) -> None:
        if self._id != ArtHeader._id:
            raise ArtParseError(f"invalid artnet header id: `{self._id!r}'")

        if not ArtOp(self.op_code):
            raise ArtParseError("unknown artnet opcode {self.op_code}")


@dataclass(frozen=True)
class ArtHeaderProtVer:
    """
    separated protocol version from the art-net header because for some reason
    ArtPollReply does not include it...
    """

    # ArtNet protocol revision number high
    prot_ver_high: U8 = U8(0)

    # ArtNet protocol revision number low
    prot_ver_low: U8 = U8(14)

    def __post_init__(self) -> None:
        if (
            self.prot_ver_high < ArtHeaderProtVer.prot_ver_high
            or self.prot_ver_low < ArtHeaderProtVer.prot_ver_low
        ):
            raise ArtParseError(
                f"invalid artnet protocol version: {self.prot_ver_high} {self.prot_ver_low}"
            )
