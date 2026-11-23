"""Teacher credentials and live Long Valley classes."""

from dataclasses import dataclass, field
from hashlib import sha256
import secrets
from threading import Event, Lock
from time import monotonic
from typing import Optional

from .investigation import ACCESS_ROUTES, ALIGNMENTS, CROSSING_TYPES, Comparison, Design


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
SITES = ("A", "B")
_DESIGN_FIELDS = {"alignment", "crossing_type", "access"}
_VIEWS = {"proposed", "baseline", "replay", "reset"}


@dataclass(frozen=True)
class FormReceipt:
    status: int
    notice: str = ""
    anchor: str = ""
    language_changed: bool = False


def record_comparison(collection, comparison):
    for key, previous in collection.items():
        if previous == comparison:
            return key
    key = str(len(collection) + 1)
    collection[key] = comparison
    return key


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
    starting_site: str
    language: str
    rejoin_code: str = field(repr=False)
    site: str = field(init=False)
    draft_design: Design = field(default_factory=Design)
    tested_design: Design = field(default_factory=Design)
    show_works: bool = True
    saved_design: Optional[Design] = None
    revision: int = 0
    rendered_comparisons: dict = field(default_factory=dict)

    def __post_init__(self):
        self.site = self.starting_site

    def capture_comparison(self):
        comparison = Comparison(self.site, self.tested_design)
        return record_comparison(self.rendered_comparisons, comparison), comparison

    def move_to_partner_site(self, site):
        self.site = site
        self.revision += 1
        if self.saved_design is not None:
            self.tested_design = self.saved_design
        self.draft_design = self.tested_design
        self.show_works = True

    def receive_form(self, submitted_site, action, fields, session, languages):
        """Apply a group form. A design or view counts only on this group's current site."""
        current_site = submitted_site == self.site
        draft = self.draft_design
        if current_site and (action == "design" or fields.keys() & _DESIGN_FIELDS):
            alignment = fields.get("alignment", [""])[0]
            crossing_type = fields.get("crossing_type", [""])[0]
            access_route = fields.get("access", [""])[0]
            if (alignment not in ALIGNMENTS or crossing_type not in CROSSING_TYPES
                    or access_route not in ACCESS_ROUTES):
                return FormReceipt(400)
            draft = Design(alignment, crossing_type, access_route)

        language_changed = False
        anchor = "#spring-comparison"
        notice = ""
        if action == "language":
            preferred = fields.get("language", [""])[0]
            if preferred not in languages:
                return FormReceipt(400)
            self.language = preferred
            language_changed = True
            anchor = ""

        if action == "share":
            comparison = self.rendered_comparisons.get(fields.get("comparison", [""])[0])
            if comparison is None:
                return FormReceipt(400)
            session.share_comparison(comparison)
            notice = "shared"
            if not current_site or fields.get("revision", [""])[0] != str(self.revision):
                return FormReceipt(303, notice, anchor, language_changed)

        if not current_site:
            return FormReceipt(303, "swapped", "#current-site", language_changed)

        if action == "design":
            self.tested_design = draft
            self.show_works = True
            if fields.get("save") == ["1"] and not session.swapped:
                self.saved_design = draft
                notice = "saved"
        elif action == "view":
            view = fields.get("view", [""])[0]
            if view not in _VIEWS:
                return FormReceipt(400)
            self.show_works = view != "baseline"
            if view == "reset":
                draft = self.tested_design = Design()
                anchor = "#spring-investigation"
            elif view == "replay":
                notice = "replayed"
        self.draft_design = draft
        self.revision += 1
        return FormReceipt(303, notice, anchor, language_changed)


@dataclass
class ClassSession:
    code: str
    teacher: str
    language: str
    expires_at: float
    groups: dict = field(default_factory=dict)
    swapped: bool = False
    comparisons: dict = field(default_factory=dict)
    swap_or_end: Event = field(default_factory=Event, init=False, repr=False, compare=False)

    def remaining_seconds(self):
        return max(0.0, self.expires_at - monotonic())

    def occupied_sites(self):
        return {group.site for group in self.groups.values()}

    def new_rejoin_code(self):
        active_codes = {group.rejoin_code for group in self.groups.values()}
        while True:
            code = "-".join("".join(secrets.choice(CODE_ALPHABET) for _ in range(4)) for _ in range(3))
            if code not in active_codes:
                return code

    def take_site(self, site):
        if site not in SITES or site in self.occupied_sites():
            return None
        token = secrets.token_urlsafe(32)
        self.groups[token] = Group(site, self.language, self.new_rejoin_code())
        return token

    def rejoin_code_for(self, starting_site):
        return next((g.rejoin_code for g in self.groups.values() if g.starting_site == starting_site), None)

    def redeem_rejoin_code(self, entered_code):
        code = entered_code.strip().upper().replace("-", "").replace(" ", "")
        if not code.isascii():
            return None
        for token, group in self.groups.items():
            if secrets.compare_digest(group.rejoin_code.replace("-", ""), code):
                group.rejoin_code = self.new_rejoin_code()
                return token
        return None

    def share_comparison(self, comparison):
        record_comparison(self.comparisons, comparison)

    def pass_the_city(self):
        if self.swapped:
            return True
        if len(self.groups) != len(SITES):
            return False

        first, second = self.groups.values()
        first_site = first.site
        first.move_to_partner_site(second.site)
        second.move_to_partner_site(first_site)
        self.swapped = True
        self.swap_or_end.set()
        return True


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
        if session is not None and session.remaining_seconds() == 0:
            del self.classes[code]
            session.swap_or_end.set()
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
        session.swap_or_end.set()
        return True
