"""SSRF prevention module guarding against private, loopback, and cloud metadata access."""

import asyncio
import ipaddress
import socket
import urllib.parse
from collections.abc import Awaitable, Callable

BLOCKED_NETWORKS = [
    # IPv4 Private / Loopback / Link-Local / CGNAT / Broadcast / Reserved
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6 Loopback / Link-Local / Unique Local / Unspecified / Multicast
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("ff00::/8"),
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
}


class SSRFError(Exception):
    """Exception raised when an endpoint targets a prohibited internal IP or host."""


def is_blocked_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if IP is private, loopback, link-local, reserved, or otherwise non-global."""
    # Check IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1)
    if isinstance(ip_obj, ipaddress.IPv6Address):
        mapped = ip_obj.ipv4_mapped
        if mapped and is_blocked_ip(mapped):
            return True

    # Standard python attributes
    if (
        not ip_obj.is_global
        or ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    ):
        return True

    # Check explicit network ranges
    return any(ip_obj in net for net in BLOCKED_NETWORKS)


async def _resolve_hostname(hostname: str) -> list[str]:
    """Resolve hostname to list of IP addresses asynchronously."""
    loop = asyncio.get_running_loop()
    try:
        # socket.getaddrinfo returns list of (family, type, proto, canonname, sockaddr)
        addr_infos = await loop.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        return [str(entry[4][0]) for entry in addr_infos]
    except socket.gaierror as err:
        raise SSRFError(f"Failed to resolve hostname '{hostname}': {err}") from err


async def validate_url(
    url: str,
    allow_local: bool = False,
    dns_resolver: Callable[[str], Awaitable[list[str]]] | None = None,
) -> None:
    """Validate URL for allowed scheme and non-internal target hosts/IPs.

    Raises SSRFError if URL scheme is not HTTP/HTTPS or targets internal networks.
    """
    if not url or not isinstance(url, str):
        raise SSRFError("URL must be a non-empty string")

    parsed = urllib.parse.urlsplit(url.strip())

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise SSRFError(f"Disallowed scheme '{parsed.scheme}': only HTTP and HTTPS are supported")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL does not contain a valid hostname or IP address")

    # If local/test override is active, bypass host & IP checks
    if allow_local:
        return

    # Check known local hostname patterns
    lower_host = hostname.lower().strip()
    if (
        lower_host in BLOCKED_HOSTNAMES
        or lower_host.endswith(".localhost")
        or lower_host.endswith(".local")
    ):
        raise SSRFError(f"Access to host '{hostname}' is blocked for SSRF protection")

    # Check if hostname is an IP literal
    try:
        ip_obj = ipaddress.ip_address(lower_host)
    except ValueError:
        ip_obj = None

    if ip_obj is not None:
        if is_blocked_ip(ip_obj):
            raise SSRFError(f"Access to IP '{ip_obj}' is blocked for SSRF protection")
        return

    # Resolve hostname to IPs
    resolver = dns_resolver or _resolve_hostname
    ip_strings = await resolver(hostname)
    if not ip_strings:
        raise SSRFError(f"Could not resolve IP addresses for host '{hostname}'")

    for ip_str in ip_strings:
        try:
            resolved_ip = ipaddress.ip_address(ip_str)
        except ValueError as err:
            raise SSRFError(f"Invalid resolved IP '{ip_str}' for host '{hostname}': {err}") from err

        if is_blocked_ip(resolved_ip):
            raise SSRFError(
                f"Host '{hostname}' resolves to blocked IP '{resolved_ip}' (SSRF protection)"
            )
