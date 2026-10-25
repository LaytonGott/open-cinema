"""Guard test: every Python file in the director app has a module docstring."""
import ast
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"


class AppDocstringsTest(unittest.TestCase):
    def test_every_module_has_docstring(self):
        files = [p for p in APP.rglob("*.py") if "__pycache__" not in p.parts]
        self.assertTrue(files)
        for path in sorted(files):
            if path.name == "__init__.py" and path.stat().st_size == 0:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            doc = ast.get_docstring(tree)
            self.assertTrue(doc and doc.strip(), "%s has no module docstring" % path)


if __name__ == "__main__":
    unittest.main()
