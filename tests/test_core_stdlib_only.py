"""The lens math core (open_optics/) imports only the standard library and itself.

Torch and numpy are installed in the project venv for the ComfyUI node tests, so a core module that
slipped in `import torch` (even inside a function) would still pass its own tests. This test reads
every import statement in open_optics/*.py and fails on anything that is not standard library.
"""
import ast
import sys
import unittest
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent / "open_optics"


def imported_roots(source):
    roots = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


class CoreStdlibOnlyTest(unittest.TestCase):
    def test_core_modules_import_only_the_standard_library(self):
        files = sorted(CORE.glob("*.py"))
        self.assertGreater(len(files), 5)
        for path in files:
            for root in imported_roots(path.read_text(encoding="utf-8")):
                allowed = root in sys.stdlib_module_names or root == "open_optics" or root == "__future__"
                self.assertTrue(allowed, f"{path.name} imports {root}, which is not standard library")

    def test_the_check_would_catch_torch(self):
        self.assertEqual(imported_roots("import torch\nfrom numpy.linalg import norm\n"), {"torch", "numpy"})
        self.assertEqual(imported_roots("def f():\n    import torch.nn as nn\n"), {"torch"})


if __name__ == "__main__":
    unittest.main()
