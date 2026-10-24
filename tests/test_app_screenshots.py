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

    def test_working_and_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "app_screenshots.py"), "--out", tmp],
                                    capture_output=True, text=True, timeout=240)
            self.assertEqual(result.returncode, 0, result.stderr)
            for w, h in [(1280, 720), (1366, 768)]:
                for kind in ("working", "result"):
                    path = Path(tmp) / f"{kind}-{w}x{h}.png"
                    self.assertTrue(path.exists(), f"{path.name} missing")
                    self.assertEqual(png_size(path), (w, h), path.name)

    def test_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "app_screenshots.py"), "--out", tmp],
                                    capture_output=True, text=True, timeout=240)
            self.assertEqual(result.returncode, 0, result.stderr)
            for w, h in [(1280, 720), (1366, 768)]:
                path = Path(tmp) / f"failed-{w}x{h}.png"
                self.assertTrue(path.exists(), f"{path.name} missing")
                self.assertEqual(png_size(path), (w, h), path.name)

    def test_comfy_down(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "app_screenshots.py"), "--out", tmp],
                                    capture_output=True, text=True, timeout=240)
            self.assertEqual(result.returncode, 0, result.stderr)
            for w, h in [(1280, 720), (1366, 768)]:
                path = Path(tmp) / f"comfy-down-{w}x{h}.png"
                self.assertTrue(path.exists(), f"{path.name} missing")
                self.assertEqual(png_size(path), (w, h), path.name)

    def test_all_twelve_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "app_screenshots.py"), "--out", tmp],
                                    capture_output=True, text=True, timeout=240)
            self.assertEqual(result.returncode, 0, result.stderr)
            for w, h in [(1280, 720), (1366, 768)]:
                for kind in ("empty", "form", "working", "result", "failed", "comfy-down"):
                    path = Path(tmp) / f"{kind}-{w}x{h}.png"
                    self.assertTrue(path.exists(), f"{path.name} missing")
                    self.assertEqual(png_size(path), (w, h), path.name)
                    self.assertGreater(path.stat().st_size, 5 * 1024, path.name)

    def test_bad_out_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "not-a-folder"
            bad.write_text("x")
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "app_screenshots.py"), "--out", str(bad)],
                                    capture_output=True, text=True, timeout=240)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())


if __name__ == "__main__":
    unittest.main()
