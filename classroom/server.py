"""HTTP entry point for the Long Valley classroom."""

from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from ipaddress import IPv4Address
from pathlib import Path
import re
import secrets
from subprocess import SubprocessError
from threading import Thread
from time import monotonic
from typing import Union
from urllib.parse import parse_qs
import webbrowser

import qrcode
from qrcode.image.pure import PyPNGImage

from . import teacher_views, views
from .network import ClassroomLan, format_origin, has_network_settings, open_network_settings
from .state import Classroom, ClassSession, SITES


STATIC = Path(__file__).with_name("static")
SWAP_WAIT_SECONDS = 15
ASSETS = {
    "/classroom.css": ("classroom.css", "text/css; charset=utf-8"),
    "/class-status.js": ("class-status.js", "text/javascript; charset=utf-8"),
    "/join-group.js": ("join-group.js", "text/javascript; charset=utf-8"),
    "/teacher-launch.js": ("teacher-launch.js", "text/javascript; charset=utf-8"),
    "/teacher.css": ("teacher.css", "text/css; charset=utf-8"),
    "/teacher-art.svg": ("teacher-art.svg", "image/svg+xml"),
    "/teacher-scene.js": ("teacher-scene.js", "text/javascript; charset=utf-8"),
    "/teacher-sign-in.js": ("teacher-sign-in.js", "text/javascript; charset=utf-8"),
}


@dataclass
class Response:
    status: int
    body: Union[str, bytes] = ""
    headers: tuple = ()
    content_type: str = "text/html; charset=utf-8"
    cache_control: str = "no-store"


class ExpiredLaunchTicket(Exception):
    """The pending sign-in link reached the browser after its deadline."""


class TeacherLaunch:
    def __init__(self, credential, key):
        self._credential = credential
        self._authorization = f"Bearer {key}".encode()
        self._tickets = {}
        self._has_signed_in = False

    def authorizes(self, authorization):
        return secrets.compare_digest(self._authorization, authorization.encode())

    def issue_ticket(self):
        # A profile chooser can return after expiry. Keep its ticket until it requests its one renewal.
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = monotonic() + 120
        return ticket

    def is_only_pending(self, ticket):
        return not self._has_signed_in and self._tickets.keys() == {ticket}

    def redeem(self, ticket):
        expires = self._tickets.pop(ticket, None)
        if expires is None:
            return None
        if monotonic() >= expires:
            raise ExpiredLaunchTicket
        self._has_signed_in = True
        return self._credential


def student_join_path(session, *, language=None):
    return f"/join/{session.code}?lang={language or session.language}"


def group_assignment(group):
    return Response(204, headers=(("X-Current-Site", group.site),))


class Handler(BaseHTTPRequestHandler):
    def log_request(self, code="-", size="-"):
        pass

    def respond(self, response):
        data = response.body.encode() if isinstance(response.body, str) else response.body
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        if response.status != 204:
            self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", response.cache_control)
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; "
                         f"script-src 'self' 'sha256-{views.GROUP_STATUS_SCRIPT_HASH}'")
        for name, value in response.headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    @property
    def classroom(self):
        return self.server.classroom

    def cookie_value(self, name):
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return cookie[name].value if name in cookie else ""
        except CookieError:
            return ""

    def teacher_id(self):
        return self.classroom.teacher_for_session(self.cookie_value(self.server.teacher_cookie_name))

    def join_origin_for_page(self, path, fields):
        if self.server.lan is None:
            return self.server.origin
        if not path.startswith("/teacher/project/"):
            return None
        with self.classroom.lock:
            teacher = self.teacher_id()
            session = self.classroom.class_for_teacher(teacher) if teacher else None
            if session is None:
                return None
            projection = f"/teacher/project/{session.code}"
            join_status = path == projection + "/status" and fields.get("network") == ["1"]
            if not join_status and path not in (projection, projection + "/", projection + "/qr.png"):
                return None
        # Windows adapter discovery can take seconds. Groups can still act and
        # classes can expire while the teacher waits. get_page rechecks ownership.
        return self.server.lan.join_origin()

    def local_request_origin(self):
        # Match the numeric address the browser reached, including on a multi-interface host.
        address, port = self.connection.getsockname()
        origin = format_origin("http", address, port)
        if self.headers.get("Host") in (origin.removeprefix("http://"), f"{address}:{port}"):
            return origin
        return None

    def is_local_teacher_launch(self):
        return self.server.teacher_launch is not None and self.is_local_request()

    def is_local_request(self):
        return IPv4Address(self.client_address[0]).is_loopback and self.local_request_origin() == self.server.origin

    def can_open_network_settings(self):
        return self.server.lan is not None and self.is_local_request() and has_network_settings()

    def owned_class(self, code, language) -> Union[ClassSession, Response]:
        teacher = self.teacher_id()
        if teacher is None:
            return Response(403)
        session = self.classroom.active_class(code)
        if session is None:
            return Response(410, views.unavailable(language))
        if session.teacher != teacher:
            return Response(403)
        return session

    def session_cookie(self, name, value, path, *, clear=False):
        secure = "; Secure" if self.server.origin.startswith("https://") else ""
        max_age = "; Max-Age=0" if clear else ""
        return f"{name}={value}; Path={path}; HttpOnly; SameSite=Strict{secure}{max_age}"

    def sign_in_teacher(self, credential):
        token = self.classroom.sign_in(credential) if credential else None
        if token is None:
            return None
        return self.session_cookie(self.server.teacher_cookie_name, token, "/teacher")

    def redirect(self, path, *cookies):
        headers = [("Location", path)]
        headers.extend(("Set-Cookie", cookie) for cookie in cookies if cookie)
        return Response(303, headers=tuple(headers))

    def closed_join(self, code, language, *, override=None):
        preferred = override if override in views.LANGUAGES else self.cookie_value("group_language")
        return Response(410, views.unavailable(
            preferred if preferred in views.LANGUAGES else language, join_code=code,
        ))

    def request_target(self):
        path, _, query = self.path.partition("?")
        fields = parse_qs(query, keep_blank_values=True)
        language = fields.get("lang", ["en"])[0]
        return path, language if language in views.LANGUAGES else "en", fields

    def do_GET(self):
        path, language, fields = self.request_target()
        if path in ASSETS:
            name, content_type = ASSETS[path]
            return self.respond(Response(200, (STATIC / name).read_bytes(), content_type=content_type))
        if path.startswith("/join/") and path.endswith("/status"):
            code = path.removeprefix("/join/").removesuffix("/status")
            response = self.group_status(code, wait_for_swap=fields.get("wait") == ["swap"])
            try:
                return self.respond(response)
            except (BrokenPipeError, ConnectionResetError):
                # A group can leave the page while the request is waiting for a swap.
                return
        join_origin = self.join_origin_for_page(path, fields)
        with self.classroom.lock:
            response = self.get_page(path, language, fields, join_origin)
        self.respond(response)

    def group_status(self, code, *, wait_for_swap):
        with self.classroom.lock:
            session = self.classroom.active_class(code)
            if session is None:
                return Response(410)
            group = session.groups.get(self.cookie_value("group_session"))
            if group is None:
                return Response(403)
            if not wait_for_swap or session.swapped:
                return group_assignment(group)
            timeout = min(SWAP_WAIT_SECONDS, session.remaining_seconds())

        session.swap_or_end.wait(timeout)
        with self.classroom.lock:
            if self.classroom.active_class(code) is None:
                return Response(410)
            return group_assignment(group)

    def get_page(self, path, language, fields, join_origin):
        if path == "/":
            return Response(200, views.home(language))
        if path == "/teacher/launch" and self.is_local_teacher_launch():
            return Response(200, teacher_views.sign_in(language, launching=True))
        if path in ("/teacher", "/teacher/lessons") or path.startswith("/teacher/lessons/"):
            teacher = self.teacher_id()
            if teacher is None:
                return Response(200, teacher_views.sign_in(language))
            session = self.classroom.class_for_teacher(teacher)
            if session and "lang" not in fields:
                language = session.language
            if path.startswith("/teacher/lessons/"):
                lesson = path.removeprefix("/teacher/lessons/")
                if lesson not in teacher_views.LESSONS:
                    return Response(404)
                if session and lesson == teacher_views.CLASSROOM_LESSON:
                    return self.redirect(f"/teacher?lang={language}")
                return Response(200, teacher_views.lesson_review(language, lesson))
            if path == "/teacher/lessons" or session is None:
                return Response(200, teacher_views.lesson_list(language, session))
            return Response(200, teacher_views.live_lesson(
                language, session, notice=fields.get("notice", [""])[0], track_network=self.server.lan is not None,
                local_settings=self.can_open_network_settings(),
            ))
        if path == "/join":
            if "code" not in fields:
                return Response(200, views.find_class(language))
            code = fields["code"][0].strip().upper()
            session = self.classroom.active_class(code)
            if session:
                return self.redirect(student_join_path(session))
            return Response(410, views.unavailable(language, join_code=code))
        if path.startswith("/join/"):
            code = path.removeprefix("/join/")
            session = self.classroom.active_class(code)
            if session is None:
                override = fields.get("closed-language", [""])[0]
                return self.closed_join(code, language, override=override)
            group = session.groups.get(self.cookie_value("group_session"))
            if group:
                # Browser history can reuse the hidden page while offline.
                # Ordinary requests revalidate, and the controls still wait for an assignment.
                return Response(
                    200, views.group_opening(
                        session, group, swap_wait_seconds=SWAP_WAIT_SECONDS,
                        notice=fields.get("notice", [""])[0],
                    ),
                    headers=(("Vary", "Cookie"),), cache_control="private, no-cache",
                )
            return Response(200, views.choose_site(
                session, taken="taken" in fields, invalid_rejoin=fields.get("notice") == ["invalid-rejoin"],
            ))
        if path.startswith("/classes/"):
            code, _, action = path.removeprefix("/classes/").partition("/")
            if action == "status":
                session = self.classroom.active_class(code)
                if session is None:
                    return Response(410)
                return Response(204, headers=(("X-Sites-Swapped", str(session.swapped).lower()),))
        if path.startswith("/teacher/project/"):
            code, _, detail = path.removeprefix("/teacher/project/").partition("/")
            return self.teacher_projection(code, detail, language, join_origin, fields)
        if path.startswith("/teacher/rejoin/"):
            session = self.owned_class(path.removeprefix("/teacher/rejoin/"), language)
            if isinstance(session, Response):
                return session
            site = fields.get("site", [""])[0]
            if site not in SITES:
                return Response(400)
            language = language if "lang" in fields else session.language
            return Response(200, teacher_views.teacher_rejoin(language, session, site))
        return Response(404, views.unavailable(language))

    def teacher_projection(self, code, detail, language, join_origin, fields):
        session = self.owned_class(code, language)
        if isinstance(session, Response):
            return session

        if detail == "status":
            headers = ()
            if join_origin and fields.get("network") == ["1"]:
                headers = (("X-Join-Url", join_origin + student_join_path(session)),)
            return Response(204, headers=headers)
        if detail == "comparisons":
            return Response(200, views.shared_comparisons(session))
        if detail == "comparisons/feed":
            return Response(200, views.comparison_choices(session))
        if detail.startswith("comparisons/"):
            comparison = session.comparisons.get(detail.removeprefix("comparisons/"))
            if comparison is not None:
                return Response(200, views.comparison_projection(session, comparison))
        join_url = join_origin + student_join_path(session) if join_origin else None
        if detail == "qr.png":
            if join_url is None or fields.get("join", [join_url]) != [join_url]:
                return Response(503)
            image = BytesIO()
            qrcode.make(join_url, image_factory=PyPNGImage, box_size=8).save(image)
            return Response(200, image.getvalue(), content_type="image/png")
        if detail == "":
            return Response(200, views.projection(session, join_url, track_network=self.server.lan is not None))
        return Response(404, views.unavailable(session.language))

    def do_POST(self):
        path, language, _ = self.request_target()
        if path == "/teacher/launch-ticket":
            return self.respond(self.reopen_teacher())
        expected = self.local_request_origin() if self.server.lan is not None else self.server.origin
        if expected is None or self.headers.get("Origin") != expected:
            return self.respond(Response(403))
        size = self.headers.get("Content-Length", "")
        if not size.isascii() or not size.isdecimal() or len(size) > 4:
            return self.respond(Response(400))
        fields = parse_qs(self.rfile.read(int(size)).decode("utf-8", errors="replace"))
        if path == "/teacher/network-settings":
            return self.respond(self.teacher_network_settings(fields, language))
        with self.classroom.lock:
            response = self.post_page(path, language, fields)
        self.respond(response)

    def teacher_network_settings(self, fields, language):
        if not self.can_open_network_settings():
            return Response(403)
        with self.classroom.lock:
            session = self.owned_class(fields.get("code", [""])[0], language)
            if isinstance(session, Response):
                return session
        try:
            open_network_settings()
        except (OSError, SubprocessError):
            return Response(503)
        return Response(204)

    def reopen_teacher(self):
        if (not self.is_local_teacher_launch() or self.headers.get("Origin") is not None
                or not self.server.teacher_launch.authorizes(self.headers.get("Authorization", ""))):
            return Response(403)
        with self.classroom.lock:
            if self.server.browser_open_failed:
                return Response(503)
            ticket = self.server.teacher_launch.issue_ticket()
        return Response(200, ticket, content_type="text/plain; charset=utf-8")

    def post_page(self, path, language, fields):
        if path == "/teacher/launch" and self.is_local_teacher_launch():
            launch = self.server.teacher_launch
            try:
                credential = launch.redeem(fields.get("ticket", [""])[0])
            except ExpiredLaunchTicket:
                # Only the local browser opener receives the replacement link.
                open_teacher_browser(self.server)
                return Response(202)
            if credential is None:
                return Response(403)
            if self.teacher_id() is not None:
                return Response(204)
            cookie = self.sign_in_teacher(credential)
            if cookie is None:
                return Response(403)
            return Response(204, headers=(("Set-Cookie", cookie),))
        if path == "/teacher/sign-in":
            credential = fields.get("credential", [""])[0]
            if not credential:
                return Response(400, teacher_views.sign_in(language, error="missing_credential"))
            cookie = self.sign_in_teacher(credential.strip())
            if cookie is None:
                return Response(401, teacher_views.sign_in(language, error="bad_credential"))
            return self.redirect(f"/teacher?lang={language}", cookie)
        if path == "/teacher/sign-out":
            self.classroom.sign_out(self.cookie_value(self.server.teacher_cookie_name))
            cookie = self.session_cookie(self.server.teacher_cookie_name, "", "/teacher", clear=True)
            return self.redirect(f"/teacher?lang={language}", cookie)
        if path == "/teacher/start":
            teacher = self.teacher_id()
            opening_language = fields.get("language", [""])[0]
            if teacher is None:
                return Response(403)
            if opening_language not in views.LANGUAGES:
                return Response(400)
            if fields.get("lesson", [teacher_views.CLASSROOM_LESSON]) != [teacher_views.CLASSROOM_LESSON]:
                return Response(400)
            self.classroom.start(teacher, opening_language)
            if self.server.lan is not None:
                # An adapter lookup from the last class can still be in flight.
                self.server.lan = ClassroomLan(self.server.server_port)
            return self.redirect("/teacher")
        if path == "/teacher/end":
            teacher = self.teacher_id()
            code = fields.get("code", [""])[0]
            if teacher is None or not self.classroom.end(teacher, code):
                return Response(403)
            return self.redirect(f"/teacher?lang={language}")
        if path == "/teacher/pass-the-city":
            code = fields.get("code", [""])[0]
            session = self.owned_class(code, language)
            if isinstance(session, Response):
                return session
            if not session.pass_the_city():
                return self.redirect(f"/teacher?lang={language}&notice=waiting-for-groups")
            return self.redirect(f"/teacher?lang={language}")
        if path.startswith("/join/"):
            code, separator, action = path.removeprefix("/join/").partition("/")
            if separator:
                return self.group_action(code, action, language, fields)
        return Response(404, views.unavailable(language))

    def group_entry(self, session, action, token, fields):
        join_path = student_join_path(session)
        if token in session.groups:
            return Response(200) if action == "resume" else self.redirect(join_path)

        browser_key = fields.get("browser_key", [""])[0]
        if not re.fullmatch(r"[0-9a-f]{32}", browser_key):
            return Response(400)
        if action == "resume":
            token = session.group_token_for_browser(browser_key)
            if token is None:
                return Response(204)
        elif action == "take-site":
            token = session.take_site(fields.get("site", [""])[0], browser_key=browser_key)
            if token is None:
                return self.redirect(f"{join_path}&taken=1")
        else:
            token = session.redeem_rejoin_code(fields.get("rejoin_code", [""])[0], browser_key=browser_key)
            if token is None:
                return self.redirect(f"{join_path}&notice=invalid-rejoin#rejoin-group")

        path = f"/join/{session.code}"
        cookies = (
            self.session_cookie("group_session", token, path),
            self.session_cookie("group_language", session.groups[token].language, path),
        )
        if action == "resume":
            return Response(200, headers=tuple(("Set-Cookie", cookie) for cookie in cookies))
        return self.redirect(join_path, *cookies)

    def group_action(self, code, action, language, fields):
        session = self.classroom.active_class(code)
        if session is None:
            return self.closed_join(code, language)
        token = self.cookie_value("group_session")
        if action in {"take-site", "rejoin", "resume"}:
            return self.group_entry(session, action, token, fields)
        group = session.groups.get(token)
        if group is None or action not in {"language", "design", "view", "share"}:
            return Response(404)
        receipt = group.receive_form(
            fields.get("site", [""])[0], action, fields, session, views.LANGUAGES,
        )
        if receipt.status != 303:
            return Response(receipt.status)
        language_cookie = None
        if receipt.language_changed:
            language_cookie = self.session_cookie("group_language", group.language, f"/join/{code}")
        join_path = student_join_path(session, language=group.language if session.swapped else None)
        notice = f"&notice={receipt.notice}" if receipt.notice else ""
        return self.redirect(f"{join_path}{notice}{receipt.anchor}", language_cookie)


def open_teacher_browser(server, *, initial=False):
    launch = server.teacher_launch
    ticket = launch.issue_ticket()
    # The browser fragment keeps the single-use ticket out of HTTP requests and referrers.
    url = f"{server.origin}/teacher/launch#{ticket}"

    def open_browser():
        try:
            if webbrowser.open_new_tab(url):
                return
        except Exception:
            pass
        with server.classroom.lock:
            # A foreground opener can report failure after sign-in or renewal.
            if not initial or not launch.is_only_pending(ticket):
                return
            server.browser_open_failed = True
        server.shutdown()

    # Foreground browser commands may wait for the page or even for the browser to exit.
    Thread(target=open_browser, daemon=True).start()


def run(host, port, public_url, duration_seconds, credentials, *, register_launcher=None):
    automatic_network = host is None and public_url is None
    bind_host = host or ("0.0.0.0" if automatic_network else "127.0.0.1")
    with ThreadingHTTPServer((bind_host, port), Handler) as server:
        server.classroom = Classroom(credentials, duration_seconds)
        server.origin = public_url or format_origin("http", "127.0.0.1", server.server_port)
        server.lan = ClassroomLan(server.server_port) if automatic_network else None
        server.teacher_cookie_name = "teacher_session"
        server.teacher_launch = None
        server.browser_open_failed = False
        if register_launcher is not None:
            # Separate installations can serve different classrooms. Browsers share cookies across ports.
            server.teacher_cookie_name = f"teacher_session_{server.server_port}"
            server.teacher_launch = TeacherLaunch(credentials.issue(), register_launcher(server.server_port))
            open_teacher_browser(server, initial=True)
        else:
            print(server.origin, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return
        if server.browser_open_failed:
            raise SystemExit("SiMetropolis Edu couldn't open your default browser.")
