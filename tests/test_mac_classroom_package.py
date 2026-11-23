"""Verify the extracted Mac download through Launch Services on a logged-in Mac."""

from contextlib import contextmanager
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import plistlib
import shlex
import shutil
import signal
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic, sleep
import unittest
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ARCHIVE = os.environ.get("SIMETROPOLIS_MAC_TEST_ARCHIVE")


@unittest.skipUnless(sys.platform == "darwin", "requires macOS")
class MacClassroomPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = TemporaryDirectory(prefix="mac-classroom-package-")
        cls.addClassCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        cls.archive = folder / "SiMetropolis-Edu-Mac.zip"
        subprocess.run([sys.executable, ROOT / "tools/build_mac_classroom.py", cls.archive], check=True)
        if RUNTIME_ARCHIVE:
            cls.driver = folder / "classroom-test-driver"
            subprocess.run(["/usr/bin/xcrun", "swiftc", "-module-cache-path", folder / "swift-cache",
                            ROOT / "tests/MacClassroomDriver.swift", "-o", cls.driver], check=True)

    def setUp(self):
        temporary = TemporaryDirectory(prefix="mac-classroom-launch-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        extracted = self.folder / "Teacher Downloads"
        subprocess.run(["/usr/bin/ditto", "-x", "-k", self.archive, extracted], check=True)
        self.app = extracted / "Open SiMetropolis Edu.app"

    def test_the_download_extracts_to_one_classroom_launcher_for_both_mac_architectures(self):
        self.assertEqual(list(self.app.parent.iterdir()), [self.app])
        with (self.app / "Contents/Info.plist").open("rb") as plist:
            executable = plistlib.load(plist)["CFBundleExecutable"]
        binary = self.app / "Contents/MacOS" / executable
        architectures = subprocess.check_output(["/usr/bin/lipo", "-archs", binary], text=True)
        self.assertEqual(set(architectures.split()), {"arm64", "x86_64"})
        subprocess.run(["/usr/bin/codesign", "--verify", "--strict", self.app], check=True)

    @unittest.skipUnless(RUNTIME_ARCHIVE, "set SIMETROPOLIS_MAC_TEST_ARCHIVE to the native runtime tarball")
    def test_a_fresh_mac_opens_private_lesson_preparation_and_can_relaunch_offline(self):
        self.exercise_first_launch(interrupt=False)

    @unittest.skipUnless(RUNTIME_ARCHIVE and os.environ.get("SIMETROPOLIS_MAC_TEST_RETRY") == "1",
                         "set SIMETROPOLIS_MAC_TEST_ARCHIVE and SIMETROPOLIS_MAC_TEST_RETRY=1 for the Accessibility test")
    def test_retry_after_an_interrupted_transfer_opens_private_lesson_preparation(self):
        self.exercise_first_launch(interrupt=True)

    def exercise_first_launch(self, interrupt):
        with serve_runtime(Path(RUNTIME_ARCHIVE)) as (url, requested, connected):
            manifest_path = self.app / "Contents/Resources/runtime.json"
            manifest = json.loads(manifest_path.read_text())
            runtime = manifest[platform.machine()]
            runtime["url"] = url
            manifest_path.write_text(json.dumps(manifest))
            subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", self.app], check=True)
            if not interrupt:
                connected.set()
            with self.launch_app() as browser_url:
                self.assertTrue(requested.wait(15), "The fresh launcher did not request the runtime")
                if interrupt:
                    wait = subprocess.run([self.driver, "wait-for-retry", self.app])
                    if wait.returncode == 77:
                        self.skipTest("The test runner needs macOS Accessibility access to press Retry")
                    wait.check_returncode()
                    self.assertFalse(browser_url.exists(), "The classroom opened during an incomplete download")
                    connected.set()
                    subprocess.run([self.driver, "retry", self.app], check=True)
                self.assert_lesson_preparation(browser_url)
            application_support = self.folder / "Library/Application Support"
            runtime_directory = application_support / "org.simetropolis.edu" / ("runtime-" + runtime["sha256"])
            self.assertTrue((runtime_directory / "python/bin/python3").is_file(), "Runtime escaped the test home")
        with self.launch_app() as browser_url:
            self.assert_lesson_preparation(browser_url)

    @contextmanager
    def launch_app(self):
        browser_url = self.folder / "browser-url"
        browser_url.unlink(missing_ok=True)
        opener = self.folder / "test-browser"
        pending = shlex.quote(str(self.folder / "pending-browser-url"))
        opener.write_text("#!/bin/sh\n" + record_browser_url_and_parent_pid(
            pending, shlex.quote(str(browser_url))))
        opener.chmod(0o700)
        subprocess.run(["/usr/bin/open", "-n", "--arch", platform.machine(), "--env", f"CFFIXED_USER_HOME={self.folder}",
                        "--env", f"TMPDIR={self.folder}", "--env", f'BROWSER="{opener}" %s', self.app], check=True)
        try:
            yield browser_url
        finally:
            try:
                subprocess.run([self.driver, "quit", self.app], check=True)
            finally:
                if browser_url.exists():
                    url, parent_pid = browser_url.read_text().splitlines()
                    port = urlsplit(url).port
                    deadline = monotonic() + 5
                    while accepts_connection(port):
                        if monotonic() >= deadline:
                            os.kill(int(parent_pid), signal.SIGTERM)
                            self.fail("The classroom still accepted connections after its launcher quit")
                        sleep(0.1)

    def assert_lesson_preparation(self, browser_url):
        deadline = monotonic() + 30
        while not browser_url.exists() and monotonic() < deadline:
            sleep(0.1)
        self.assertTrue(browser_url.exists(), "The launcher did not open the browser")
        entry = urlsplit(browser_url.read_text().splitlines()[0])
        self.assertEqual(entry.hostname, "127.0.0.1")
        self.assertEqual(entry.path, "/teacher/launch")
        browser = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
        origin = entry._replace(path="", fragment="").geturl()
        launch = Request(entry._replace(fragment="").geturl(), urlencode({"ticket": entry.fragment}).encode(),
                         headers={"Origin": origin})
        with browser.open(launch, timeout=5) as response:
            self.assertEqual(response.status, 204)
        with browser.open(entry._replace(path="/teacher", fragment="").geturl(), timeout=5) as response:
            self.assertIn(b"Start class", response.read())


DROPPED_BODY_OCTETS = 32 * 1024


def record_browser_url_and_parent_pid(pending, published):
    return f'printf "%s\\n%s\\n" "$1" "$PPID" > {pending}\nmv {pending} {published}\n'


def accepts_connection(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(("127.0.0.1", port)) == 0


@contextmanager
def serve_runtime(archive):
    requested = Event()
    connected = Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requested.set()
            self.send_response(200)
            self.send_header("Content-Length", str(archive.stat().st_size))
            self.end_headers()
            with archive.open("rb") as runtime:
                if connected.is_set():
                    shutil.copyfileobj(runtime, self.wfile)
                else:
                    self.wfile.write(runtime.read(DROPPED_BODY_OCTETS))

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/python.tar.gz", requested, connected
        finally:
            server.shutdown()
            thread.join()
