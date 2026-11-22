"""Start or reopen one classroom for a prepared installation."""

import errno
from http.client import HTTPConnection, HTTPException
import os
import re
import secrets
from tempfile import TemporaryDirectory
from pathlib import Path
from time import monotonic, sleep
import webbrowser

from .state import TeacherCredentials


def take_service_lock(lock):
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        if error.errno not in {errno.EACCES, errno.EAGAIN}:
            raise
        return False
    return True


def existing_browser_url(registration):
    try:
        port_text, key = registration.read_text(encoding="ascii").split()
        port = int(port_text)
    except (FileNotFoundError, ValueError):
        return None
    if not 1 <= port <= 65535 or not re.fullmatch(r"[A-Za-z0-9_-]{43}", key):
        return None

    connection = HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        connection.request("POST", "/teacher/launch-ticket", headers={"Authorization": f"Bearer {key}"})
        response = connection.getresponse()
        if response.status == 200:
            ticket = response.read(44).decode("ascii")
            if re.fullmatch(r"[A-Za-z0-9_-]{43}", ticket):
                return f"http://127.0.0.1:{port}/teacher/launch#{ticket}"
    except (OSError, HTTPException, UnicodeError):
        return None
    finally:
        connection.close()
    return None


def launch(data_dir, duration_seconds):
    from .server import run

    directory = data_dir / "launcher"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    registration = directory / "running"

    def register(port):
        key = secrets.token_urlsafe(32)
        registration.touch(mode=0o600, exist_ok=False)
        registration.write_text(f"{port} {key}", encoding="ascii")
        return key

    # Keep the lock for the service's lifetime. The OS releases it even if the launcher is killed.
    descriptor = os.open(directory / "service.lock", os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "r+b") as lock:
        deadline = monotonic() + 10
        while not take_service_lock(lock):
            url = existing_browser_url(registration)
            if url is not None:
                try:
                    if webbrowser.open_new_tab(url):
                        return
                except (OSError, webbrowser.Error):
                    pass
                raise SystemExit("SiMetropolis Edu couldn't open your default browser.")
            if monotonic() >= deadline:
                raise SystemExit("The running SiMetropolis Edu classroom hasn't responded. Try opening Edu again.")
            sleep(0.1)

        registration.unlink(missing_ok=True)
        try:
            with TemporaryDirectory(prefix="simetropolis-edu-") as data:
                run(None, 0, None, duration_seconds, TeacherCredentials(Path(data) / "teachers"),
                    register_launcher=register)
        finally:
            registration.unlink(missing_ok=True)
