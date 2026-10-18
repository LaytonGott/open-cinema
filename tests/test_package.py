import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STDLIB_ONLY_CODE = (
    "import sys; before = set(sys.modules); import open_optics; "
    "print(sorted(m for m in {n.split('.')[0] for n in set(sys.modules) - before} "
    "if m not in sys.stdlib_module_names and not m.startswith('_') "
    "and m != 'open_optics' and m != '__main__'))"
)


class TestPackage(unittest.TestCase):
    def test_import_is_silent(self):
        result = subprocess.run(
            [sys.executable, "-c", "import open_optics"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_import_is_stdlib_only(self):
        result = subprocess.run(
            [sys.executable, "-c", STDLIB_ONLY_CODE],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "[]")

    def test_all_names_exist(self):
        import open_optics
        for name in open_optics.__all__:
            self.assertTrue(hasattr(open_optics, name), name)


if __name__ == "__main__":
    unittest.main()
