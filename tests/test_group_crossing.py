"""A form for the site a group has left cannot replace the crossing it carried."""

import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classroom.investigation import Design
from classroom.server import Handler
from classroom.state import Classroom, TeacherCredentials


ROOT = Path(__file__).resolve().parents[1]
CROSSING_FIELDS = {
    "draft_design", "tested_design", "saved_design", "show_works", "site", "revision", "language",
}


def crossing_writes(source):
    """Names of crossing assignments. Group.receive_form and Group.move_to_partner_site own these."""
    found = []

    def names(target):
        if isinstance(target, ast.Attribute) and target.attr in CROSSING_FIELDS:
            owner = target.value.id if isinstance(target.value, ast.Name) else "?"
            found.append(f"{owner}.{target.attr}")
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                names(item)

    class Visitor(ast.NodeVisitor):
        def visit_Assign(self, node):
            for target in node.targets:
                names(target)
            self.generic_visit(node)

        def visit_AugAssign(self, node):
            names(node.target)
            self.generic_visit(node)

    Visitor().visit(ast.parse(source))
    return found


class GroupCrossingTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        credentials = TeacherCredentials(Path(self.directory.name))
        self.classroom = Classroom(credentials, 3600)
        teacher = self.classroom.sign_in(credentials.issue())
        self.session = self.classroom.start(teacher, "en")
        self.token_a = self.session.take_site("A")
        self.session.take_site("B")
        self.group = self.session.groups[self.token_a]
        self.saved = Design("central", "tunnel", "valley")
        self.unsaved = Design("south", "elevated", "east")
        self.group.saved_design = self.saved
        self.group.tested_design = self.unsaved
        self.group.draft_design = self.unsaved
        self.assertTrue(self.session.pass_the_city())

    def post(self, action, fields):
        handler = Handler.__new__(Handler)
        handler.headers = {"Cookie": f"group_session={self.token_a}"}
        handler.server = type("Server", (), {
            "origin": "http://127.0.0.1:8899", "classroom": self.classroom,
        })()
        return handler.group_action(self.session.code, action, "en", fields)

    def stale_form(self, **extra):
        fields = {
            "site": ["A"],
            "alignment": [self.unsaved.alignment],
            "crossing_type": [self.unsaved.crossing_type],
            "access": [self.unsaved.access_route],
            "revision": ["0"],
        }
        fields.update(extra)
        return fields

    def test_a_language_switch_for_the_old_site_keeps_the_carried_crossing(self):
        response = self.post("language", self.stale_form(language=["zh-Hant"]))

        self.assertEqual(response.status, 303)
        location = dict(response.headers)["Location"]
        self.assertIn("notice=swapped", location)
        self.assertIn("lang=zh-Hant", location)
        self.assertEqual(self.group.language, "zh-Hant")
        self.assertEqual(self.group.site, "B")
        self.assertEqual(self.group.tested_design, self.saved)
        self.assertEqual(self.group.draft_design, self.saved)
        self.assertIn("group_language=zh-Hant", dict(response.headers)["Set-Cookie"])

    def test_a_design_posted_for_the_old_site_keeps_the_carried_crossing(self):
        response = self.post("design", self.stale_form(save=["1"]))

        self.assertIn("notice=swapped", dict(response.headers)["Location"])
        self.assertEqual(self.group.tested_design, self.saved)
        self.assertEqual(self.group.saved_design, self.saved)
        self.assertEqual(self.group.draft_design, self.saved)

    def test_a_design_posted_for_the_current_site_replaces_the_crossing(self):
        replacement = Design("north", "elevated", "east")
        response = self.post("design", {
            "site": ["B"],
            "alignment": [replacement.alignment],
            "crossing_type": [replacement.crossing_type],
            "access": [replacement.access_route],
            "revision": [str(self.group.revision)],
        })

        self.assertNotIn("notice=swapped", dict(response.headers)["Location"])
        self.assertEqual(self.group.tested_design, replacement)
        self.assertEqual(self.group.draft_design, replacement)

    def test_an_invalid_language_does_not_change_the_carried_crossing(self):
        response = self.post("language", self.stale_form(language=["fr"]))

        self.assertEqual(response.status, 400)
        self.assertEqual(self.group.language, "en")
        self.assertEqual(self.group.tested_design, self.saved)

    def test_the_http_handler_cannot_write_a_groups_crossing(self):
        offenders = []
        for path in sorted((ROOT / "classroom").rglob("*.py")):
            if path.name == "state.py":
                continue
            for name in crossing_writes(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.relative_to(ROOT)} assigns {name}")
        self.assertEqual(
            offenders, [],
            "Change a group's crossing through Group.receive_form or "
            "Group.move_to_partner_site in classroom/state.py",
        )
