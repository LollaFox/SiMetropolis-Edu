"""Only the classroom service process may change the Mac launcher window."""

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LaunchLifetimeTests(unittest.TestCase):
    def test_reopen_helper_cannot_replace_or_close_the_live_class(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            binary = folder / "launch-lifetime"
            source = folder / "main.swift"
            lifetime = ROOT / "tools/mac_classroom/LaunchLifetime.swift"
            check = ROOT / "tests/LaunchLifetimeCheck.swift"
            source.write_text(lifetime.read_text(encoding="utf-8") + "\n" + check.read_text(encoding="utf-8"),
                              encoding="utf-8")
            compiled = subprocess.run([
                "/usr/bin/xcrun", "swiftc", "-module-cache-path", str(folder / "swift-cache"),
                source, "-o", binary,
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            checked = subprocess.run([binary], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
