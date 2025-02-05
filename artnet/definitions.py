from ipaddress import IPv4Address
from typing import NewType, NamedTuple


ARTNET_POLL_INTERVAL_S = 2.5
DMX_REFRESH_RATE_MAX_HZ = 44

PortAddr = NewType("PortAddr", int)


class Universe(NamedTuple):
    ip: IPv4Address
    port_addr: PortAddr
