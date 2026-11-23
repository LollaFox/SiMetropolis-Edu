"""Deterministic classroom LAN selection checks. No network configuration is changed."""

import socket
import struct
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from classroom import network


MAC_INTERFACES = """\
utun2: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1500
    inet 10.1.0.23 --> 10.1.0.23 netmask 0xffffffff
en3: flags=8863<UP,BROADCAST,RUNNING,MULTICAST> mtu 1500
    inet 10.1.1.4 netmask 0xffffff00 broadcast 10.1.1.255
    status: inactive
en0: flags=8863<UP,BROADCAST,RUNNING,MULTICAST> mtu 1500
    inet 10.1.2.3 netmask 0xffffff00 broadcast 10.1.2.255
    status: active
"""


class ClassroomNetworkTests(unittest.TestCase):
    def test_physical_wifi_with_a_vpn_and_disconnected_ethernet(self):
        with patch.object(sys, "platform", "darwin"), patch.object(network, "_output", return_value=MAC_INTERFACES):
            with patch.object(socket, "socket") as route:
                self.assertEqual(network.local_join_origin(80), "http://10.1.2.3")
                route.assert_not_called()

    def test_default_route_breaks_ties_only_between_eligible_addresses(self):
        candidates = "10.1.2.3\n10.1.3.4\n"
        with patch.object(sys, "platform", "win32"), patch.object(network, "_output", return_value=candidates):
            with patch.object(socket, "socket") as sock:
                route = sock.return_value.__enter__.return_value
                route.getsockname.return_value = ("10.1.3.4", 0)
                self.assertEqual(network.local_join_origin(8080), "http://10.1.3.4:8080")
                route.getsockname.return_value = ("10.1.0.23", 0)
                self.assertEqual(network.local_join_origin(8080), "http://10.1.2.3:8080")
                route.connect.side_effect = OSError("no gateway")
                self.assertEqual(network.local_join_origin(8080), "http://10.1.2.3:8080")

    def test_prefer_an_assigned_address_but_allow_link_local_only_lans(self):
        with patch.object(sys, "platform", "win32"):
            with patch.object(network, "_output", return_value="169.254.1.2\n172.40.1.3\n"):
                self.assertEqual(network.local_join_origin(8080), "http://172.40.1.3:8080")
            with patch.object(network, "_output", return_value="169.254.1.2\n"):
                self.assertEqual(network.local_join_origin(8080), "http://169.254.1.2:8080")

    def test_no_eligible_interface_or_unavailable_utility(self):
        for platform in ("darwin", "win32"):
            with self.subTest(platform=platform), patch.object(sys, "platform", platform):
                for failure in (FileNotFoundError(), subprocess.TimeoutExpired("lookup", 5)):
                    with patch.object(subprocess, "check_output", side_effect=failure):
                        self.assertIsNone(network.local_join_origin(8080))
        with patch.object(sys, "platform", "win32"):
            with patch.object(network, "_output", return_value="\nwarning\n127.0.0.1\n0.0.0.0\n224.0.0.1\n"):
                self.assertIsNone(network.local_join_origin(8080))

    def test_linux_hardware_precedes_container_ethernet_and_ignores_tunnels(self):
        interfaces = [(1, "tun0"), (2, "eth0"), (3, "wlan0")]
        addresses = {"eth0": "172.18.0.2", "wlan0": "10.1.2.3"}

        def ioctl(probe, operation, request):
            name = request.split(b"\0", 1)[0].decode()
            if operation == network.SIOCGIFFLAGS:
                return bytes(16) + struct.pack("H", network.READY_INTERFACE)
            return bytes(20) + socket.inet_aton(addresses[name])

        with patch.dict(sys.modules, fcntl=SimpleNamespace(ioctl=ioctl)), patch.object(sys, "platform", "linux"):
            with patch.object(socket, "if_nameindex", return_value=interfaces):
                with patch.object(network.Path, "exists", lambda path: path.parent.name == "wlan0"):
                    self.assertEqual(network.local_join_origin(8899), "http://10.1.2.3:8899")
                interfaces.pop()
                with patch.object(network.Path, "exists", return_value=False):
                    self.assertEqual(network.local_join_origin(8899), "http://172.18.0.2:8899")

    def test_canonical_cli_origins(self):
        self.assertEqual(network.format_origin("http", "127.0.0.1", 80), "http://127.0.0.1")
        self.assertEqual(network.format_origin("https", "::1", 443), "https://[::1]")
        self.assertEqual(network.format_origin("https", "::1", 8443), "https://[::1]:8443")
        self.assertEqual(network.format_origin("http", "café.edu", None), "http://xn--caf-dma.edu")

    def test_teacher_refreshes_the_lan_and_the_projection_reuses_its_address(self):
        lan = network.ClassroomLan(8899)
        address = "http://10.1.2.3:8899"
        with patch.object(network, "monotonic", return_value=1), \
             patch.object(network, "local_join_origin", side_effect=[None, address]) as discover:
            self.assertIsNone(lan.join_origin())
            self.assertEqual(lan.join_origin(refresh=True), address)
            self.assertEqual(lan.join_origin(), address)
            self.assertEqual(discover.call_count, 2)


if __name__ == "__main__":
    unittest.main()
