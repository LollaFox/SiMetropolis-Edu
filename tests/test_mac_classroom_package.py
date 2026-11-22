"""Verify the Mac download after extracting it with macOS archive tools."""

from contextlib import contextmanager
from hashlib import sha256
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
    def extract_package(self, folder):
        archive = folder / "SiMetropolis-Edu-Mac.zip"
        extracted = folder / "Teacher Downloads"
        subprocess.run([sys.executable, ROOT / "tools/build_mac_classroom.py", archive], check=True)
        subprocess.run(["/usr/bin/ditto", "-x", "-k", archive, extracted], check=True)
        return extracted / "Open SiMetropolis Edu.app"

    def test_the_download_extracts_to_one_classroom_launcher_for_both_mac_architectures(self):
        with TemporaryDirectory(prefix="mac-classroom-package-") as directory:
            app = self.extract_package(Path(directory))
            self.assertEqual(list(app.parent.iterdir()), [app])
            with (app / "Contents/Info.plist").open("rb") as plist:
                executable = plistlib.load(plist)["CFBundleExecutable"]
            binary = app / "Contents/MacOS" / executable
            architectures = subprocess.check_output(["/usr/bin/lipo", "-archs", binary], text=True)
            self.assertEqual(set(architectures.split()), {"arm64", "x86_64"})
            subprocess.run(["/usr/bin/codesign", "--verify", "--strict", app], check=True)

    @unittest.skipUnless(RUNTIME_ARCHIVE, "set SIMETROPOLIS_MAC_TEST_ARCHIVE to the native runtime tarball")
    def test_a_fresh_mac_opens_private_lesson_preparation_and_can_relaunch_offline(self):
        with TemporaryDirectory(prefix="mac-classroom-launch-") as directory:
            folder = Path(directory)
            app = self.extract_package(folder)
            archive = Path(RUNTIME_ARCHIVE)
            with serve_runtime(archive) as (url, requested):
                manifest = {platform.machine(): {"url": url, "sha256": sha256(archive.read_bytes()).hexdigest()}}
                (app / "Contents/Resources/runtime.json").write_text(json.dumps(manifest))
                subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", app], check=True)
                with launch_app(app, folder) as browser_url:
                    self.assertTrue(requested.wait(8), "The fresh launcher did not request the runtime")
                    self.assert_lesson_preparation(browser_url)
            # The launcher must reopen lesson preparation with its download source gone.
            with launch_app(app, folder) as browser_url:
                self.assert_lesson_preparation(browser_url)

    def assert_lesson_preparation(self, browser_url):
        deadline = monotonic() + 30
        while not browser_url.exists() and monotonic() < deadline:
            sleep(0.1)
        self.assertTrue(browser_url.exists(), "The launcher did not open the browser")
        entry = urlsplit(browser_url.read_text().strip())
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


@contextmanager
def serve_runtime(archive):
    requested = Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requested.set()
            self.send_response(200)
            self.send_header("Content-Length", str(archive.stat().st_size))
            self.end_headers()
            with archive.open("rb") as runtime:
                shutil.copyfileobj(runtime, self.wfile)

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/python.tar.gz", requested
        finally:
            server.shutdown()
            thread.join()


@contextmanager
def launch_app(app, folder):
    browser_url = folder / "browser-url"
    browser_url.unlink(missing_ok=True)
    opener = folder / "test-browser"
    opener.write_text(f'#!/bin/sh\nprintf "%s\\n" "$1" > {shlex.quote(str(browser_url))}\n')
    opener.chmod(0o700)
    environment = {**os.environ, "CFFIXED_USER_HOME": str(folder), "TMPDIR": str(folder),
                   "BROWSER": f'"{opener}" %s'}
    with subprocess.Popen(["/usr/bin/arch", f"-{platform.machine()}", app / "Contents/MacOS/OpenSiMetropolisEdu"],
                          env=environment, start_new_session=True) as launcher:
        try:
            yield browser_url
        finally:
            try:
                os.killpg(launcher.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
