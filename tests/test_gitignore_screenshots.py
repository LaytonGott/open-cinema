import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class GitignoreScreenshotsTest(unittest.TestCase):
    def test_screenshots_folder_is_ignored(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertTrue(any(line.strip() in ("app/screenshots/", "app/screenshots") for line in lines))

    def test_screenshot_script_defaults_to_ignored_folder(self):
        script = ROOT / "scripts" / "app_screenshots.py"
        if not script.exists():
            return
        text = script.read_text(encoding="utf-8")
        match = re.search(r'add_argument\("--out",\s*default=([^)]*\))', text)
        self.assertIsNotNone(match)
        self.assertIn('"app" / "screenshots"', match.group(1))


if __name__ == "__main__":
    unittest.main()
