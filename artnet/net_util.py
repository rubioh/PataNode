from typing import Tuple

from ipaddress import IPv4Address


def prefix_length_to_subnet_mask(prefix_length: int) -> Tuple[int, int, int, int]:
    if not 0 <= prefix_length <= 32:
        raise ValueError("Invalid prefix length. It must be between 0 and 32.")
    subnet_mask = (0xFFFFFFFF << (32 - prefix_length)) & 0xFFFFFFFF
    return ((subnet_mask >> i) & 0xFF for i in (24, 16, 8, 0))  #  type: ignore


def get_broadcast_address(ip: IPv4Address, network_prefix: int) -> IPv4Address:
    split_ip = parse_ip(ip)
    or_mask = (1 << (32 - network_prefix)) - 1
    ret = ".".join(
        [str(split_ip[i] | ((or_mask >> 8 * (3 - i)) & 0xFF)) for i in range(4)]
    )
    return IPv4Address(ret)


def parse_ip(ip: IPv4Address) -> Tuple[int, int, int, int]:
    a, b, c, d = (int(byte) for byte in str(ip).split("."))
    return a, b, c, d
