"""Choose a student join origin from the computer's connected IPv4 LAN adapters."""

from ipaddress import IPv4Address
from pathlib import Path
import re
import socket
import struct
import subprocess
import sys
from threading import Lock
from time import monotonic


def format_origin(scheme, host, port):
    """Format a validated origin with an unbracketed hostname."""
    host = f"[{host}]" if ":" in host else host.encode("idna").decode("ascii")
    default_port = 443 if scheme == "https" else 80
    suffix = f":{port}" if port not in {None, default_port} else ""
    return f"{scheme}://{host}{suffix}"


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


def _windows_addresses():
    # IANA interface types for Ethernet and Wi-Fi exclude cellular modems.
    # Joining by index also works with renamed or localized adapter names.
    command = (
        "$ids = (Get-NetAdapter -Physical | Where-Object { $_.InterfaceOperationalStatus -eq 1 "
        "-and $_.InterfaceType -in 6,62,69,71,117 }).ifIndex; "
        "Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred -SkipAsSource $false "
        "| Where-Object { $ids -contains $_.InterfaceIndex } | ForEach-Object { $_.IPAddress }"
    )
    return _output("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command).splitlines()


def _linux_addresses():
    import fcntl

    physical, ethernet = [], []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            for _, name in socket.if_nameindex():
                # Linux exposes physical adapters through sysfs. A CI container
                # can have just its own Ethernet endpoint and no hardware entry.
                if (Path("/sys/class/net") / name / "device").exists():
                    addresses = physical
                elif re.fullmatch(r"eth\d+|en[opsx][\w.-]+|wl[anpsx][\w.-]+", name):
                    addresses = ethernet
                else:
                    continue
                request = struct.pack("256s", name.encode())
                try:
                    flags = struct.unpack_from("H", fcntl.ioctl(probe, 0x8913, request), 16)[0]
                    # IFF_UP, IFF_BROADCAST and IFF_RUNNING
                    if flags & 0x43 != 0x43:
                        continue
                    result = fcntl.ioctl(probe, 0x8915, request)  # SIOCGIFADDR
                    addresses.append(socket.inet_ntoa(result[20:24]))
                except OSError:
                    continue
    except OSError:
        pass
    return physical or ethernet


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
    # A self-assigned address can still work on a local link with no gateway.
    addresses = [address for address in addresses if not address.is_link_local] or addresses
    if not addresses:
        return None

    selected = addresses[0]
    if len(addresses) > 1:
        # Use the route only to choose between known LAN addresses. UDP connect
        # asks the kernel which source it would use without sending a packet.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
                route.connect(("192.0.2.1", 9))
                preferred = IPv4Address(route.getsockname()[0])
            if preferred in addresses:
                selected = preferred
        except OSError:
            pass
    return format_origin("http", str(selected), port)


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
