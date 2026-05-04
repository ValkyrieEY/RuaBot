"""Helpers for displaying reachable startup URLs."""

from __future__ import annotations

import ipaddress
import socket
import urllib.request
from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class StartupUrl:
    label: str
    url: str


def _strip_ipv6_brackets(host: str) -> str:
    host = str(host or "").strip()
    if host.startswith("[") and host.endswith("]"):
        return host[1:-1]
    return host


def _format_url_host(host: str) -> str:
    host = _strip_ipv6_brackets(host)
    try:
        ip = ipaddress.ip_address(host)
        if ip.version == 6:
            return f"[{ip}]"
    except ValueError:
        pass
    return host


def _is_unspecified_host(host: str) -> bool:
    host = _strip_ipv6_brackets(host).lower()
    if host in {"", "0.0.0.0", "::"}:
        return True
    try:
        return ipaddress.ip_address(host).is_unspecified
    except ValueError:
        return False


def _is_loopback_host(host: str) -> bool:
    host = _strip_ipv6_brackets(host).lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_lan_host(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(_strip_ipv6_brackets(host))
        return ip.version == 4 and (ip.is_private or ip.is_link_local)
    except ValueError:
        return False


def _make_url(host: str, port: int) -> str:
    return f"http://{_format_url_host(host)}:{int(port)}/"


def _add_ipv4_candidate(candidates: set[str], host: str) -> None:
    try:
        ip = ipaddress.ip_address(str(host or "").strip())
    except ValueError:
        return
    if ip.version != 4:
        return
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast:
        return
    candidates.add(str(ip))


def discover_lan_ipv4_addresses() -> List[str]:
    """Return local non-loopback IPv4 addresses, preferring private LAN IPs."""
    candidates: set[str] = set()

    for target in ("8.8.8.8", "1.1.1.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(0.2)
                sock.connect((target, 80))
                _add_ipv4_candidate(candidates, sock.getsockname()[0])
        except OSError:
            pass

    for name in {socket.gethostname(), socket.getfqdn()}:
        if not name:
            continue
        try:
            for info in socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_DGRAM):
                _add_ipv4_candidate(candidates, info[4][0])
        except OSError:
            pass

    return sorted(
        candidates,
        key=lambda value: (not ipaddress.ip_address(value).is_private, value),
    )


def discover_public_ipv4_address(timeout: float = 2.0) -> Optional[str]:
    """Return the current public IPv4 address when an external service is reachable."""
    endpoints = (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
    )
    for endpoint in endpoints:
        try:
            with urllib.request.urlopen(endpoint, timeout=timeout) as response:
                value = response.read(64).decode("utf-8", errors="ignore").strip()
            ip = ipaddress.ip_address(value)
            if ip.version == 4 and not ip.is_private and not ip.is_loopback and not ip.is_unspecified:
                return str(ip)
        except Exception:
            continue
    return None


def build_startup_urls(
    bind_host: str,
    port: int,
    lan_ips: Optional[Iterable[str]] = None,
    public_ip: Optional[str] = None,
) -> List[StartupUrl]:
    """Build user-facing URLs for a listening host/port pair."""
    host = str(bind_host or "").strip()
    resolved_lan_ips = list(lan_ips) if lan_ips is not None else discover_lan_ipv4_addresses()
    urls: List[StartupUrl] = []
    seen: set[str] = set()

    def add(label: str, url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            urls.append(StartupUrl(label=label, url=url))

    if _is_unspecified_host(host):
        detected_public_ip = public_ip if public_ip is not None else discover_public_ipv4_address()
        if detected_public_ip:
            add("External", _make_url(detected_public_ip, port))
        add("Local", _make_url("127.0.0.1", port))
        for lan_ip in resolved_lan_ips:
            add("LAN", _make_url(lan_ip, port))
    elif _is_loopback_host(host):
        add("Local", _make_url(host, port))
    elif _is_lan_host(host):
        add("LAN", _make_url(host, port))
    else:
        add("Configured", _make_url(host, port))

    return urls


def append_url_path(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")
