"""Teacher credentials and live Long Valley classes."""

from dataclasses import dataclass, field
from hashlib import sha256
import secrets
from threading import Lock
from time import monotonic

from .investigation import Design


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
SITES = ("A", "B")


class TeacherCredentials:
    def __init__(self, directory):
        self.directory = directory

    def issue(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        credential = secrets.token_urlsafe(32)
        (self.directory / self._digest(credential)).touch(mode=0o600, exist_ok=False)
        return credential

    def verify(self, credential):
        digest = self._digest(credential)
        return digest if (self.directory / digest).is_file() else None

    @staticmethod
    def _digest(credential):
        return sha256(credential.encode()).hexdigest()


@dataclass
class Group:
    site: str
    language: str
    draft_design: Design = field(default_factory=Design)
    tested_design: Design = field(default_factory=Design)
    show_works: bool = True


@dataclass
class ClassSession:
    code: str
    teacher: str
    language: str
    expires_at: float
    groups: dict = field(default_factory=dict)

    def occupied_sites(self):
        return {group.site for group in self.groups.values()}

    def take_site(self, site):
        if site not in SITES or site in self.occupied_sites():
            return None
        token = secrets.token_urlsafe(32)
        self.groups[token] = Group(site, self.language)
        return token


class Classroom:
    def __init__(self, credentials, duration_seconds):
        self.credentials = credentials
        self.duration_seconds = duration_seconds
        self.lock = Lock()
        self._teacher_sessions = {}
        self.classes = {}
        self.used_codes = set()

    def sign_in(self, credential):
        teacher = self.credentials.verify(credential)
        if teacher is None:
            return None
        token = secrets.token_urlsafe(32)
        self._teacher_sessions[token] = teacher
        return token

    def teacher_for_session(self, token):
        return self._teacher_sessions.get(token)

    def sign_out(self, token):
        self._teacher_sessions.pop(token, None)

    def active_class(self, code):
        session = self.classes.get(code)
        if session is not None and session.expires_at <= monotonic():
            del self.classes[code]
            return None
        return session

    def class_for_teacher(self, teacher):
        code = next((code for code, session in self.classes.items() if session.teacher == teacher), None)
        return self.active_class(code) if code else None

    def start(self, teacher, language):
        existing = self.class_for_teacher(teacher)
        if existing is not None:
            return existing
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self.used_codes:
                break
        session = ClassSession(code, teacher, language, monotonic() + self.duration_seconds)
        self.used_codes.add(code)
        self.classes[code] = session
        return session

    def end(self, teacher, code):
        session = self.active_class(code)
        if session is None:
            return True
        if session.teacher != teacher:
            return False
        del self.classes[code]
        return True
