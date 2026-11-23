"""Choose a student join origin from the computer's connected IPv4 LAN adapters."""

from ipaddress import IPv4Address
import os
from pathlib import Path
import platform
import re
import socket
import struct
import subprocess
import sys
from threading import Lock
from time import monotonic


def format_origin(scheme, host, port):
    host = f"[{host}]" if ":" in host else host.encode("idna").decode("ascii")
    default_port = 443 if scheme == "https" else 80
    suffix = f":{port}" if port not in {None, default_port} else ""
    return f"{scheme}://{host}{suffix}"


def has_network_settings():
    return sys.platform in {"darwin", "win32"}


def open_network_settings():
    if sys.platform == "win32":
        os.startfile("ms-settings:network-status")
    elif sys.platform == "darwin":
        major = int(platform.mac_ver()[0].partition(".")[0] or "0")
        target = ("x-apple.systempreferences:com.apple.Network-Settings.extension" if major >= 13
                  else "/System/Library/PreferencePanes/Network.prefPane")
        subprocess.run(["/usr/bin/open", target], check=True, timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _output(*command):
    try:
        return subprocess.check_output(
            command, stderr=subprocess.DEVNULL, timeout=5, encoding="ascii", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return ""


def _mac_addresses():
    # Wi-Fi and Ethernet (including USB adapters) use enN on macOS.
    addresses = []
    for interface in re.split(r"\n(?=\S)", _output("/sbin/ifconfig", "-a")):
        if re.match(r"en\d+: [^\n]*\bUP\b", interface) and re.search(r"(?m)^\s+status: active$", interface):
            addresses.extend(re.findall(r"(?m)^\s+inet (\S+)", interface))
    return addresses


ETHERNET_CSMACD = 6
FAST_ETHER = 62
FAST_ETHER_FX = 69
IEEE80211 = 71
GIGABIT_ETHERNET = 117
WIRED_AND_WIFI = (ETHERNET_CSMACD, FAST_ETHER, FAST_ETHER_FX, IEEE80211, GIGABIT_ETHERNET)
SIOCGIFFLAGS = 0x8913
SIOCGIFADDR = 0x8915
IFF_UP = 0x1
IFF_BROADCAST = 0x2
IFF_RUNNING = 0x40
READY_INTERFACE = IFF_UP | IFF_BROADCAST | IFF_RUNNING
CONTAINER_ENDPOINT = re.compile(r"eth\d+|en[opsx][\w.-]+|wl[anpsx][\w.-]+")
UNSENT_ROUTE_PROBE = ("192.0.2.1", 9)


def _windows_addresses():
    interface_types = ",".join(str(kind) for kind in WIRED_AND_WIFI)
    command = (
        "$ids = (Get-NetAdapter -Physical | Where-Object { $_.InterfaceOperationalStatus -eq 1 "
        f"-and $_.InterfaceType -in {interface_types} }}).ifIndex; "
        "Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred -SkipAsSource $false "
        "| Where-Object { $ids -contains $_.InterfaceIndex } | ForEach-Object { $_.IPAddress }"
    )
    return _output("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command).splitlines()


def _linux_addresses():
    import fcntl

    physical, container = [], []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            for _, name in socket.if_nameindex():
                if (Path("/sys/class/net") / name / "device").exists():
                    addresses = physical
                elif CONTAINER_ENDPOINT.fullmatch(name):
                    addresses = container
                else:
                    continue
                request = struct.pack("256s", name.encode())
                try:
                    flags = struct.unpack_from("H", fcntl.ioctl(probe, SIOCGIFFLAGS, request), 16)[0]
                    if (flags & READY_INTERFACE) != READY_INTERFACE:
                        continue
                    result = fcntl.ioctl(probe, SIOCGIFADDR, request)
                    addresses.append(socket.inet_ntoa(result[20:24]))
                except OSError:
                    continue
    except OSError:
        pass
    return physical or container


def local_join_origin(port):
    if sys.platform == "darwin":
        candidates = _mac_addresses()
    elif sys.platform == "win32":
        candidates = _windows_addresses()
    elif sys.platform.startswith("linux"):
        candidates = _linux_addresses()
    else:
        return None

    addresses = []
    for candidate in candidates:
        try:
            address = IPv4Address(candidate)
        except ValueError:
            continue
        if not (address.is_loopback or address.is_unspecified or address.is_multicast or address.is_reserved):
            addresses.append(address)
    addresses = _prefer_routable(addresses)
    if not addresses:
        return None

    selected = addresses[0]
    if len(addresses) > 1:
        try:
            preferred = _source_chosen_by_route()
            if preferred in addresses:
                selected = preferred
        except OSError:
            pass
    return format_origin("http", str(selected), port)


def _prefer_routable(addresses):
    routable = [address for address in addresses if not address.is_link_local]
    return routable or addresses


def _source_chosen_by_route():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
        route.connect(UNSENT_ROUTE_PROBE)
        return IPv4Address(route.getsockname()[0])


class ClassroomLan:
    """Share one adapter lookup across the teacher screen, projection and QR."""

    def __init__(self, port):
        self.port = port
        self._lock = Lock()
        self._origin = None
        self._refresh_after = 0

    def join_origin(self, *, refresh=False):
        with self._lock:
            if refresh or monotonic() >= self._refresh_after:
                self._origin = local_join_origin(self.port)
                self._refresh_after = monotonic() + 5
            return self._origin

    def abandon_lookup(self):
        return ClassroomLan(self.port)
