import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def png_size(path):
    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", data[16:24])


class AppScreenshotsTest(unittest.TestCase):
    def test_empty_and_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "app_screenshots.py"), "--out", tmp],
                                    capture_output=True, text=True, timeout=240)
            self.assertEqual(result.returncode, 0, result.stderr)
            for w, h in [(1280, 720), (1366, 768)]:
                for kind in ("empty", "form"):
                    path = Path(tmp) / f"{kind}-{w}x{h}.png"
                    self.assertTrue(path.exists(), f"{path.name} missing")
                    self.assertEqual(png_size(path), (w, h), path.name)


if __name__ == "__main__":
    unittest.main()
