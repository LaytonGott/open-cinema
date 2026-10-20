import ast
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestAppImport(unittest.TestCase):
    def test_import_is_silent(self):
        result = subprocess.run(
            [sys.executable, "-c", "import app.shot, app.graphs"],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": REPO_ROOT},
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_imports_are_stdlib_only_and_bench_free(self):
        for name in ("__init__.py", "shot.py", "graphs.py"):
            path = os.path.join(REPO_ROOT, "app", name)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level > 0:
                        continue
                    modules = [node.module]
                else:
                    continue
                for module in modules:
                    top = module.split(".")[0]
                    with self.subTest(file=name, module=module):
                        self.assertTrue(
                            top in sys.stdlib_module_names or top in ("open_optics", "app"),
                            f"{name} imports {module}",
                        )
                        self.assertNotIn("bench", module)


if __name__ == "__main__":
    unittest.main()
