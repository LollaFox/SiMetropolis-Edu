import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "https://github.com/LollaFox/SiMetropolis-Edu/releases/latest/download/"


class TeacherStartupTests(unittest.TestCase):
    def test_each_readme_opens_with_both_platform_downloads(self):
        for readme, mac_label, windows_label in [
            ("README.md", "Download for Mac", "Download for Windows"),
            ("README_ZH.md", "下載 Mac 版", "下載 Windows 版"),
        ]:
            with self.subTest(readme=readme):
                introduction = (ROOT / readme).read_text(encoding="utf-8").split("\n## ", 1)[0]
                links = dict(re.findall(r"\[([^]]+)\]\(([^)]+)\)", introduction))
                self.assertEqual(
                    {label: links.get(label) for label in (mac_label, windows_label)},
                    {
                        mac_label: RELEASE + "SiMetropolis-Edu-Mac.zip",
                        windows_label: RELEASE + "SiMetropolis-Edu-Windows.zip",
                    },
                )

    def test_both_quick_starts_send_teachers_to_the_downloads_and_edu(self):
        for guide, readme in [("QuickStart.txt", "README.md"), ("打开说明.txt", "README_ZH.md")]:
            with self.subTest(guide=guide):
                instructions = (ROOT / guide).read_text(encoding="utf-8")
                self.assertIn(readme, instructions)
                self.assertIn("Open SiMetropolis Edu", instructions)
                self.assertNotRegex(instructions, r"Configure|DeepSeek|start_(product|integrated)\.py")
