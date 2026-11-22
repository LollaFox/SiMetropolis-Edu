"""HTTP entry point for the Long Valley classroom."""

from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Union
from urllib.parse import parse_qs

import qrcode
from qrcode.image.pure import PyPNGImage

from . import views
from .investigation import (
    ACCESS_ROUTES, ALIGNMENTS, CROSSING_TYPES, DEFAULT_SEASON, SEASONAL_HABITAT, STAGES, Design,
)
from .state import Classroom


STATIC = Path(__file__).with_name("static")
ASSETS = {
    "/classroom.css": ("classroom.css", "text/css; charset=utf-8"),
    "/class-status.js": ("class-status.js", "text/javascript; charset=utf-8"),
    "/season-playback.js": ("season-playback.js", "text/javascript; charset=utf-8"),
}


@dataclass
class Response:
    status: int
    body: Union[str, bytes] = ""
    headers: tuple = ()
    content_type: str = "text/html; charset=utf-8"


def student_join_path(session):
    return f"/join/{session.code}?lang={session.language}"


class Handler(BaseHTTPRequestHandler):
    def log_request(self, code="-", size="-"):
        pass

    def respond(self, response):
        data = response.body.encode() if isinstance(response.body, str) else response.body
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        if response.status != 204:
            self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
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
        return self.classroom.teacher_for_session(self.cookie_value("teacher_session"))

    def session_cookie(self, name, value, path, *, clear=False):
        secure = "; Secure" if self.server.origin.startswith("https://") else ""
        max_age = "; Max-Age=0" if clear else ""
        return f"{name}={value}; Path={path}; HttpOnly; SameSite=Strict{secure}{max_age}"

    def redirect(self, path, cookie=None):
        headers = [("Location", path)]
        if cookie:
            headers.append(("Set-Cookie", cookie))
        return Response(303, headers=tuple(headers))

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
        with self.classroom.lock:
            response = self.get_page(path, language, fields)
        self.respond(response)

    def get_page(self, path, language, fields):
        if path == "/":
            return Response(200, views.home(language))
        if path == "/teacher":
            teacher = self.teacher_id()
            if teacher is None:
                return Response(200, views.sign_in(language))
            session = self.classroom.class_for_teacher(teacher)
            return Response(200, views.teacher(session.language if session else language, session))
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
                return Response(410, views.unavailable(language, join_code=code))
            group = session.groups.get(self.cookie_value("group_session"))
            if group:
                season = fields.get("season", [DEFAULT_SEASON])[0]
                if season not in SEASONAL_HABITAT:
                    season = DEFAULT_SEASON
                if fields.get("explore") == ["year"]:
                    return Response(200, views.wetland_comparison(session, group, season=season))
                return Response(200, views.group_opening(
                    session, group, season=season, notice=fields.get("notice", [""])[0],
                ))
            return Response(200, views.choose_site(session, taken="taken" in fields))
        if path.startswith("/classes/"):
            code, _, action = path.removeprefix("/classes/").partition("/")
            if action == "status":
                return Response(204 if self.classroom.active_class(code) else 410)
        if path.startswith("/teacher/project/"):
            code, _, detail = path.removeprefix("/teacher/project/").partition("/")
            if detail in {"", "qr.png"}:
                teacher = self.teacher_id()
                if teacher is None:
                    return Response(403)
                session = self.classroom.active_class(code)
                if session is None:
                    return Response(410, views.unavailable(language))
                if session.teacher != teacher:
                    return Response(403)
                join_url = self.server.origin + student_join_path(session)
                if detail == "qr.png":
                    image = BytesIO()
                    qrcode.make(join_url, image_factory=PyPNGImage, box_size=8).save(image)
                    return Response(200, image.getvalue(), content_type="image/png")
                return Response(200, views.projection(session, join_url))
        return Response(404, views.unavailable(language))

    def do_POST(self):
        path, language, _ = self.request_target()
        if self.headers.get("Origin") != self.server.origin:
            return self.respond(Response(403))
        size = self.headers.get("Content-Length", "")
        if not size.isascii() or not size.isdecimal() or len(size) > 4:
            return self.respond(Response(400))
        fields = parse_qs(self.rfile.read(int(size)).decode("utf-8", errors="replace"))
        with self.classroom.lock:
            response = self.post_page(path, language, fields)
        self.respond(response)

    def post_page(self, path, language, fields):
        if path == "/teacher/sign-in":
            token = self.classroom.sign_in(fields.get("credential", [""])[0].strip())
            if token is None:
                return Response(401, views.sign_in(language, invalid=True))
            cookie = self.session_cookie("teacher_session", token, "/teacher")
            return self.redirect(f"/teacher?lang={language}", cookie)
        if path == "/teacher/sign-out":
            self.classroom.sign_out(self.cookie_value("teacher_session"))
            cookie = self.session_cookie("teacher_session", "", "/teacher", clear=True)
            return self.redirect(f"/teacher?lang={language}", cookie)
        if path == "/teacher/start":
            teacher = self.teacher_id()
            opening_language = fields.get("language", [""])[0]
            if teacher is None:
                return Response(403)
            if opening_language not in views.LANGUAGES:
                return Response(400)
            self.classroom.start(teacher, opening_language)
            return self.redirect("/teacher")
        if path == "/teacher/end":
            teacher = self.teacher_id()
            code = fields.get("code", [""])[0]
            if teacher is None or not self.classroom.end(teacher, code):
                return Response(403)
            return self.redirect(f"/teacher?lang={language}")
        if path.startswith("/join/"):
            code, separator, action = path.removeprefix("/join/").partition("/")
            if separator:
                return self.group_action(code, action, language, fields)
        return Response(404, views.unavailable(language))

    def group_action(self, code, action, language, fields):
        session = self.classroom.active_class(code)
        if session is None:
            return Response(410, views.unavailable(language, join_code=code))
        join_path = student_join_path(session)
        group = session.groups.get(self.cookie_value("group_session"))
        if action == "take-site":
            if group:
                return self.redirect(join_path)
            token = session.take_site(fields.get("site", [""])[0])
            if token is None:
                return self.redirect(f"{join_path}&taken=1")
            cookie = self.session_cookie("group_session", token, f"/join/{code}")
            return self.redirect(join_path, cookie)
        if group is None or action not in {"language", "design", "view"}:
            return Response(404)

        season = fields.get("season", [DEFAULT_SEASON])[0]
        if season not in SEASONAL_HABITAT:
            return Response(400)

        draft = group.draft_design
        design_fields = {"alignment", "crossing_type", "access", "construction_season"}
        if action == "design" or fields.keys() & design_fields:
            alignment = fields.get("alignment", [""])[0]
            crossing_type = fields.get("crossing_type", [""])[0]
            access_route = fields.get("access", [""])[0]
            construction_season = fields.get("construction_season", [draft.construction_season])[0]
            if (alignment not in ALIGNMENTS or crossing_type not in CROSSING_TYPES
                    or access_route not in ACCESS_ROUTES or construction_season not in SEASONAL_HABITAT):
                return Response(400)
            draft = Design(alignment, crossing_type, access_route, construction_season)

        explore_year = action in {"view", "language"} and fields.get("explore") == ["year"]
        anchor = "#crossing-comparison"
        notice = ""
        if action == "language":
            preferred = fields.get("language", [""])[0]
            if preferred not in views.LANGUAGES:
                return Response(400)
            group.language = preferred
            anchor = ""
        elif action == "design":
            group.tested_design = draft
            group.show_works = True
        elif not explore_year:
            view = fields.get("view", [""])[0]
            if view == "reset":
                draft = group.tested_design = Design()
                group.show_works = True
                group.stage = "construction"
                season = DEFAULT_SEASON
                anchor = "#crossing-investigation"
            elif view == "replay":
                group.show_works = True
                notice = "&notice=replayed"
            elif view in {"proposed", "baseline"}:
                group.show_works = view == "proposed"
            elif view in STAGES:
                group.stage = view
            elif view in SEASONAL_HABITAT:
                season = view
            else:
                return Response(400)
        group.draft_design = draft
        season_query = f"&season={season}" if season != DEFAULT_SEASON else ""
        if explore_year:
            return self.redirect(f"/join/{session.code}?lang={group.language}{season_query}&explore=year")
        return self.redirect(f"{join_path}{season_query}{notice}{anchor}")


def run(host, port, public_url, duration_seconds, credentials):
    with ThreadingHTTPServer((host, port), Handler) as server:
        server.classroom = Classroom(credentials, duration_seconds)
        server.origin = public_url or f"http://127.0.0.1:{server.server_port}"
        print(server.origin, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
