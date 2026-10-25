"""Guard test: the director app's static files load nothing from the internet."""
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
SVG_NAMESPACE = "http://www.w3.org/"


class DesignGuardTest(unittest.TestCase):
    def test_no_external_urls(self):
        files = [p for p in STATIC.rglob("*") if p.suffix in (".html", ".css", ".js")]
        self.assertTrue(files)
        for path in files:
            text = path.read_text(encoding="utf-8").replace(SVG_NAMESPACE, "")
            for scheme in ("http://", "https://"):
                self.assertNotIn(scheme, text, "%s contains %s" % (path, scheme))


if __name__ == "__main__":
    unittest.main()
