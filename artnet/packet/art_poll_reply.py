from enum import IntEnum, IntFlag, auto, StrEnum
from typing import Tuple, Self, Annotated
from bytechomp import dataclass, Parser
from bytechomp.datatypes.declarations import U8, U16

from artnet.packet.base import ArtOp, ArtExtBase, ArtHeaderProtVer, ARTNET_PORT
from artnet.packet.util import zeros


class NodeReport(StrEnum):
    # Booted in debug mode (Only used in development)
    DEBUG = "0000"
    # Power On Tests successful
    POWEROK = "0001"
    # Hardware tests failed at Power On
    POWERFAIL = "0002"
    # Last UDP from Node failed due to truncated length, Most likely caused by a collision.
    SOCKETWR1 = "0003"
    # Unable to identify last UDP transmission. Check OpCode and packet length.
    PARSEFAIL = "0004"
    # Unable to open Udp Socket in last transmission attempt
    UDPFAIL = "0005"
    # Confirms that Port Name programming via ArtAddress, was successful.
    SHNAMEOK = "0006"
    # Confirms that Long Name programming via ArtAddress, was successful.
    LONAMEOK = "0007"
    # DMX512 receive errors detected.
    DMXERROR = "0008"
    # Ran out of internal DMX transmit buffers.
    DMXUDPFULL = "0009"
    # Ran out of internal DMX Rx buffers.
    DMXRXFULL = "000a"
    # Rx Universe switches conflict.
    SWITCHERR = "000b"
    # Product configuration does not match firmware.
    CONFIGERR = "000c"
    # DMX output short detected. See GoodOutput field.
    DMXSHORT = "000d"
    # Last attempt to upload new firmware failed.
    FIRMWAREFAIL = "000e"
    # User changed switch settings when address locked by remote programming. User changes ignored.
    USERFAIL = "000f"
    # Factory reset has occurred.
    FACTORYRES = "0010"


class Style(IntEnum):
    # A DMX to / from Art-Net device
    NODE = 0x00
    # A lighting console.
    CONTROLLER = 0x01
    # A Media Server.
    MEDIA = 0x02
    # A network routing device.
    ROUTE = 0x03
    # A backup device.
    BACKUP = 0x04
    # A configuration or diagnostic tool.
    CONFIG = 0x05
    # A visualiser.
    VISUAL = 0x06


class Status2(IntFlag):
    WEB_CONFIG_SUPPORT = auto()
    DHCP_CONFIGURED = auto()
    DHCP_CAPABLE = auto()
    PORT_ADDR_15_BIT_SUPPORT = auto()
    SACN_SWITCH_SUPPORT = auto()
    SQUAWKING = auto()
    OUTPUT_STYLE_SWITCH_SUPPORT = auto()
    RDM_ART_CMD_SUPPORT = auto()


@dataclass
class PortType:
    class Protocol(IntEnum):
        DMX512 = 0b000000
        MIDI = 0b000001
        AVAB = 0b000010
        COLORTRAN_CMX = 0b000011
        ADB_62_5 = 0b000100
        ART_NET = 0b000101
        DALI = 0b000110

    protocol: Protocol
    can_input: bool
    can_output: bool

    @classmethod
    def parse(cls, n: int):
        assert n < 256
        protocol = cls.Protocol(n & 0x3F)
        can_input = bool(n & (1 << 6))
        can_output = bool(n & (1 << 7))
        return cls(protocol, can_input, can_output)

    def serialize(self) -> int:
        n = self.protocol.value
        if self.can_input:
            n += 1 << 6
        if self.can_output:
            n += 1 << 7
        return n


@dataclass(frozen=True)
class ArtPollReplyPayload:
    # Array containing the Node’s IP address. First
    # array entry is most significant byte of address.
    # When binding is implemented, bound nodes may
    # share the root node’s IP Address and the
    # BindIndex is used to differentiate the nodes.
    ip_address: Annotated[bytes, 4]
    # The Port is always 0x1936
    port: U16
    # Node’s firmware revision number. The Controller should only use this field to decide if a firmware update should proceed. The convention is that a higher number is a more recent release of firmware
    vers_info_h: U8
    vers_info_l: U8
    # Bits 14-8 of the 15 bit Port-Address are encoded into the bottom 7 bits of this field. This is used in combination with SubSwitch and SwIn[] or SwOut[] to produce the full universe address.
    net_switch: U8
    # Bits 7-4 of the 15 bit Port-Address are encoded into the bottom 4 bits of this field. This is used in combination with NetSwitch and SwIn[] or SwOut[] to produce the full universe address.
    sub_switch: U8
    # The Oem code uniquely identifies the product.
    oem_hi: U8
    oem: U8
    # This field contains the firmware version of the User Bios Extension Area (UBEA). If the UBEA is not programmed, this field contains zero.
    ubea_version: U8
    # General Status register containing bit fields as follows.
    status_1: U8
    # The ESTA manufacturer code
    esta_man_lo: U8
    esta_man_hi: U8
    # The array represents a null terminated name for each port of the node. The Controller uses the ArtAddress packet to program this string. Max length is 17 characters plus the null. This is a fixed length field, although the string it contains can be shorter than the field. An identical LongName must be reported in device with multiple binds.
    # also called short_name on website. the name refers to device
    port_name: Annotated[bytes, 18]
    # The array represents a null terminated long name for the Node. The Controller uses the ArtAddress packet to program this string. Max length is 63 characters plus the null. This is a fixed length field, although the string it contains can be shorter than the field. An identical LongName must be reported in device with multipl e binds.
    long_name: Annotated[bytes, 64]
    # The array is a textual report of the Node’s operating status or operational errors. It is primarily intended for ‘engineering’ data rathe r than ‘end user’ data. The field is formatted as:
    # “#xxxx [yyyy..] zzzzz…”
    # xxxx is a hex status code as defined in Table 3.
    # yyyy is a decimal counter that increments every time the Node sends an ArtPollResponse.
    # This allows the controller to monitor event
    # changes in the Node. zzzz is an English text string defining the status.
    # This is a fixed length field, although the string it
    # contains can be shorter than the field.
    node_report: Annotated[bytes, 64]
    # the word describing the number of input or output ports. The high byte is for future expansion and is currently zero.
    # If number of inputs is not equal to number of outputs, the largest value is taken. Zero is a legal value if no input or output ports are implemented. The maximum value is 4.  Nodes can ignore this field as the information is implicit in PortTypes[].
    num_ports_hi: U8
    num_ports_lo: U8
    # This array defines the operation and protocol of each channel. (A product with 4 inputs and 4 outputs would report 0xc0, 0xc0, 0xc0, 0xc0). The array length is fixed, independent of the number of inputs or outputs physically available on the Node.
    port_types: Annotated[bytes, 4]
    # This array defines input status of the node.
    good_input: Annotated[bytes, 4]
    # This array defines output status of the node
    good_output_a: Annotated[bytes, 4]
    # Bits 3-0 of the 15 bit Port-Address for each of the 4 possible input ports are encoded into the low nibble
    sw_in: Annotated[bytes, 4]
    # Bits 3-0 of the 15 bit Port-Address for each of the 4 possible output ports are encoded into the low nibble.
    sw_out: Annotated[bytes, 4]
    # The sACN priority value that will be used when any received DMX is converted to sACN.
    acn_priority: U8
    # If the Node supports macro key inputs, this byte represents the trigger values. The Node is responsible for ‘debouncing’ inputs. When the ArtPollReply is set to transmit automatically, (Flags Bit 1), the ArtPollReply will be sent on both key down and key up events. However, the Controller should not assume that only one bit position has changed.  The Macro inputs are used for remote event triggering or cueing.  Bit fields are active high.
    sw_macro: U8
    # If the Node supports remote trigger inputs, this byte represents the trigger values. The Node is responsible for ‘debouncing’ inputs. When the ArtPollReply is set to transmit automatically, (Flags Bit 1), the ArtPollReply will be sent on both key down and key up events. However, the Controller should not assume that only one bit position has changed.  The Remote inputs are used for remote event triggering or cueing.  Bit fields are active high
    sw_remote: U8
    # Not used, set to zero
    _spare: Annotated[bytes, 3]
    # The Style code defines the equipment style of the device. See Table 4 for current Style codes
    style: U8
    # MAC Address Hi Byte. Set to zero if node cannot supply this information.
    mac: Annotated[bytes, 6]


@dataclass(frozen=True)
class ArtPollReplyPayloadExt:
    # If this unit is part of a larger or modular product, this is the IP of the root device.
    bind_ip: Annotated[bytes, 4] = zeros(4)
    # This number represents the order of bound devices. A lower number means closer to root device. A value of 0 or 1 means root device
    bind_index: U8 = U8(0)
    # bitfield as defined in enum Status2
    status_2: U8 = U8(0)
    # This array defines output status of the node.
    good_output_b: Annotated[bytes, 4] = zeros(4)
    # bitfield controlling fail-over, switching port type, llrp etc
    status_3: U8 = U8(0)
    # RDMnet & LLRP Default Responder UID MSB
    default_resp_uid: Annotated[bytes, 6] = zeros(6)
    # Available for user specific data
    user_hi: U8 = U8(0)
    user_lo: U8 = U8(0)
    # RefreshRate allows the device to specify the maximum refresh rate, expressed in Hz, at which it can process ArtDmx
    # This is designed to allow refresh rates above DMX512 rates, for gateways that implement other protocols such as SPI. A value of 0 to 44 represents the maximum DMX512 rate of 44Hz.
    refresh_rate_hi: U8 = U8(0)
    refresh_rate_lo: U8 = U8(0)
    # Transmit as zero. For future expansion
    filler: Annotated[bytes, 11] = zeros(11)


class ArtPollReply(ArtExtBase[ArtPollReplyPayload, ArtPollReplyPayloadExt]):
    """
    The ArtPollReply message is the only one that does not include protocol
    version information. Thus we skip its parsing by
    implementing no-ops for {parse,serialize}_protocol_version.
    """

    _parser = Parser[ArtPollReplyPayload]().build()
    _extension_parser = Parser[ArtPollReplyPayloadExt]().build()
    op_code = ArtOp.POLLREPLY

    @classmethod
    def parse_protocol_version(
        cls, packet: bytes
    ) -> Tuple[ArtHeaderProtVer | None, bytes]:
        return None, packet

    def serialize_protocol_version(self) -> bytes:
        return b""

    @classmethod
    def new(
        cls,
        ip_address: Annotated[bytes, 4],
        port_address: int,
        send_count: int,
    ) -> Self:
        status = U8(0)
        port_name = b"PataShade"
        send_count %= 10000
        device_status = "ACME Art-Net Product. PataShade running"
        node_report = (
            f"#{NodeReport.POWEROK.value} [{send_count:04}] {device_status}"
        ).encode("ascii")
        node_report += zeros(64 - len(node_report))
        port_types = bytes(
            [
                PortType(PortType.Protocol.DMX512, False, False).serialize()
                for _ in range(4)
            ]
        )

        n = cls(
            ArtPollReplyPayload(
                ip_address=ip_address,
                port=U16(ARTNET_PORT),
                vers_info_h=U8(0),
                vers_info_l=U8(1),
                net_switch=U8((port_address >> 8) & 0x7F),
                sub_switch=U8(port_address & 0x70),
                oem_hi=U8(0),
                oem=U8(0),
                ubea_version=U8(0),
                status_1=status,
                esta_man_lo=U8(0),
                esta_man_hi=U8(0),
                port_name=port_name + zeros(18 - len(port_name)),
                long_name=port_name + zeros(64 - len(port_name)),
                node_report=node_report,
                num_ports_hi=U8(0),
                num_ports_lo=U8(0),
                port_types=port_types,
                good_input=zeros(4),
                good_output_a=zeros(4),
                sw_in=zeros(4),
                sw_out=zeros(4),
                acn_priority=U8(0),
                sw_macro=U8(0),
                sw_remote=U8(0),
                _spare=zeros(3),
                style=U8(Style.CONTROLLER.value),
                mac=zeros(6),
            )
        )
        # n.payload_ext = ArtPollReplyPayloadExt() #TODO
        return n
