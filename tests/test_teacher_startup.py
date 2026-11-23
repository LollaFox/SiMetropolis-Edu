"""Teacher-facing startup documents share one Mac command and do not launch the simulator."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAC_COMMAND = "sh classroom/mac_teacher.sh"
ENTRY_DOCUMENTS = (
    "README.md",
    "README_ZH.md",
    "QuickStart.txt",
    "打开说明.txt",
    "classroom/README.md",
    "backend/README.md",
    "docs/backend-v0.1.0-release/BACKEND_RELEASE_README.md",
    "docs/底部数据看板与证据过滤说明_2026-10-16.md",
    "sandbox/README.md",
)
SIMULATOR_LAUNCHES = (
    "python3 -B -m backend.server",
    "python3 -m backend.server",
    "start.command",
    "start_product.py",
    "start_integrated.py",
    "/releases/latest/download/",
)


def simulator_launches(text):
    return [phrase for phrase in SIMULATOR_LAUNCHES if phrase in text]


class TeacherStartupTests(unittest.TestCase):
    def test_mac_startup_commands_live_in_one_script(self):
        script = (ROOT / "classroom/mac_teacher.sh").read_text(encoding="utf-8")
        setup = script.index("python3 -m venv .venv")
        install = script.index(".venv/bin/python -m pip install -r classroom/requirements.txt")
        launch = script.index(".venv/bin/python -B -m classroom launch")
        self.assertLess(setup, install)
        self.assertLess(install, launch)
        for readme in ("README.md", "README_ZH.md"):
            with self.subTest(readme=readme):
                instructions = (ROOT / readme).read_text(encoding="utf-8")
                commands = re.findall(r"```sh\n(.*?)\n```", instructions, re.DOTALL)
                self.assertEqual(
                    commands, [MAC_COMMAND],
                    f"Mac startup belongs in classroom/mac_teacher.sh. {readme} should run `{MAC_COMMAND}`.",
                )
                self.assertIn("start-product.cmd", instructions)
                self.assertNotIn("python3 -m venv", instructions)

    def test_entry_documents_do_not_launch_the_simulator(self):
        for name in ENTRY_DOCUMENTS:
            with self.subTest(document=name):
                found = simulator_launches((ROOT / name).read_text(encoding="utf-8"))
                self.assertEqual(
                    found, [],
                    f"{name} launches the simulator ({', '.join(found)}). "
                    f"Point teachers at `{MAC_COMMAND}` instead.",
                )

    def test_both_quick_starts_point_to_the_mac_instructions_and_windows_shortcut(self):
        for guide, readme in [("QuickStart.txt", "README.md"), ("打开说明.txt", "README_ZH.md")]:
            with self.subTest(guide=guide):
                instructions = (ROOT / guide).read_text(encoding="utf-8")
                self.assertIn(readme, instructions)
                self.assertIn("Open SiMetropolis Edu.cmd", instructions)
                self.assertNotRegex(instructions, r"Configure|DeepSeek|start_(product|integrated)\.py|python3 -m venv")
                self.assertEqual(simulator_launches(instructions), [])
