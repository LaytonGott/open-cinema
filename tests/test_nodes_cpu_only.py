"""The node package must stay on the CPU: no GPU device use anywhere."""

import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Built from pieces so the forbidden words are not spelled out here.
FORBIDDEN = [
    "." + "cuda(",
    "cu" + "da",
    "torch." + "compile",
    "device" + "=",
    '.to("' + "cuda",
    "m" + "ps",
    "pin_" + "memory",
]


def _node_files():
    files = [os.path.join(ROOT, "__init__.py")]
    for dirpath, _dirs, names in os.walk(os.path.join(ROOT, "open_optics_nodes")):
        for name in names:
            if name.endswith(".py"):
                files.append(os.path.join(dirpath, name))
    return files


class TestNodesCpuOnly(unittest.TestCase):
    def test_no_gpu_device_use(self):
        files = _node_files()
        self.assertGreaterEqual(len(files), 5)
        for path in files:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for word in FORBIDDEN:
                self.assertNotIn(word, text, f"{word!r} found in {path}")


if __name__ == "__main__":
    unittest.main()
