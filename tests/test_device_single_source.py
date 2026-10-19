"""Only open_optics_nodes/device.py may decide the device or import ComfyUI."""

import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEVICE_PY = os.path.join(ROOT, "open_optics_nodes", "device.py")
SKIP_DIRS = {"tests", "scripts", ".venv", "node_modules", ".git", "__pycache__"}

# Built from pieces so the forbidden strings are not spelled out here.
FORBIDDEN = [
    "torch." + "compile",
    "." + "cuda(",
    'device="' + "cuda" + '"',
    "device='" + "cuda" + "'",
    'torch.device("' + "cuda",
    "import " + "comfy",
    "from " + "comfy",
]


def _repo_files():
    files = [os.path.join(ROOT, "__init__.py")]
    for package in ("open_optics", "open_optics_nodes"):
        for dirpath, dirs, names in os.walk(os.path.join(ROOT, package)):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in names:
                if name.endswith(".py"):
                    files.append(os.path.join(dirpath, name))
    return files


class TestDeviceSingleSource(unittest.TestCase):
    def test_single_device_decision_point(self):
        files = _repo_files()
        self.assertIn(DEVICE_PY, files)
        self.assertGreaterEqual(len(files), 10)
        for path in files:
            if path == DEVICE_PY:
                continue
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for word in FORBIDDEN:
                self.assertNotIn(word, text, f"{word!r} found in {path}")
        with open(DEVICE_PY, encoding="utf-8") as f:
            self.assertNotIn(FORBIDDEN[0], f.read())


if __name__ == "__main__":
    unittest.main()
