import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TeacherStartupTests(unittest.TestCase):
    def test_each_readme_can_prepare_and_launch_the_classroom_from_a_mac_terminal(self):
        for readme in ("README.md", "README_ZH.md"):
            with self.subTest(readme=readme):
                instructions = (ROOT / readme).read_text(encoding="utf-8")
                commands = "\n".join(re.findall(r"```sh\n(.*?)\n```", instructions, re.DOTALL))
                setup = commands.index("python3 -m venv .venv")
                install = commands.index(".venv/bin/python -m pip install -r classroom/requirements.txt")
                launch = commands.index(".venv/bin/python -m classroom launch")
                self.assertLess(setup, install)
                self.assertLess(install, launch)
                self.assertIn("start-product.cmd", instructions)
                self.assertNotIn("/releases/latest/download/", instructions)

    def test_both_quick_starts_point_to_the_mac_instructions_and_windows_shortcut(self):
        for guide, readme in [("QuickStart.txt", "README.md"), ("打开说明.txt", "README_ZH.md")]:
            with self.subTest(guide=guide):
                instructions = (ROOT / guide).read_text(encoding="utf-8")
                self.assertIn(readme, instructions)
                self.assertIn("Open SiMetropolis Edu.cmd", instructions)
                self.assertNotRegex(instructions, r"Configure|DeepSeek|start_(product|integrated)\.py")
