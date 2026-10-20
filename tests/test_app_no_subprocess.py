import ast
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def _imported_modules(source):
    """Return the set of top-level module names imported anywhere in source."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


class NoSubprocessTest(unittest.TestCase):
    def test_no_subprocess_import(self):
        files = sorted(APP_DIR.glob("*.py"))
        self.assertTrue(any(f.name == "server.py" for f in files))
        self.assertTrue(any(f.name == "__main__.py" for f in files))
        for path in files:
            with self.subTest(file=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("subprocess", _imported_modules(source))


if __name__ == "__main__":
    unittest.main()
