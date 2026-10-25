"""Guard test: app tests never skip and the director app has no TODO markers."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIPS = ("skip" + "Test", "skip" + "If", "pytest." + "skip")
MARKERS = ("TO" + "DO", "XX" + "X")


class HygieneTest(unittest.TestCase):
    def test_app_tests_have_no_skips(self):
        files = [p for p in (ROOT / "tests").glob("test_app_*.py") if p.name != Path(__file__).name]
        self.assertTrue(files)
        for path in files:
            text = path.read_text(encoding="utf-8")
            for word in SKIPS:
                self.assertNotIn(word, text, "%s contains %s" % (path, word))

    def test_app_has_no_todo_markers(self):
        files = [p for p in (ROOT / "app").rglob("*") if p.suffix in (".py", ".js", ".html", ".css")]
        self.assertTrue(files)
        for path in files:
            text = path.read_text(encoding="utf-8")
            for word in MARKERS:
                self.assertNotIn(word, text, "%s contains %s" % (path, word))


if __name__ == "__main__":
    unittest.main()
