"""Guard test: the director app's static files load nothing from the internet."""
import re
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
CHECK = Path(__file__).resolve().parent.parent / "scripts" / "accept_app_design.py"
TESTID = re.compile(r"""(?:\bt|get_by_test_id)\(\s*["']([^"']+)["']""")
SVG_NAMESPACE = "http://www.w3.org/"


class DesignGuardTest(unittest.TestCase):
    def test_no_external_urls(self):
        files = [p for p in STATIC.rglob("*") if p.suffix in (".html", ".css", ".js")]
        self.assertTrue(files)
        for path in files:
            text = path.read_text(encoding="utf-8").replace(SVG_NAMESPACE, "")
            for scheme in ("http://", "https://"):
                self.assertNotIn(scheme, text, "%s contains %s" % (path, scheme))

    def test_design_testids_present(self):
        names = set(TESTID.findall(CHECK.read_text(encoding="utf-8")))
        self.assertTrue(names)
        text = "".join(p.read_text(encoding="utf-8") for p in STATIC.rglob("*") if p.is_file())
        for name in sorted(names):
            self.assertIn(name, text, "test id %s not in app/static" % name)


if __name__ == "__main__":
    unittest.main()
