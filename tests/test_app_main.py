import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class AppMainTest(unittest.TestCase):
    def test_startup_line(self):
        port = _free_port()
        comfy = f"http://127.0.0.1:{_free_port()}"
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.Popen(
                [sys.executable, "-m", "app", "--port", str(port), "--data-dir", tmp, "--comfyui", comfy],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                text=True,
            )
            try:
                line = proc.stdout.readline().rstrip("\r\n")
                self.assertEqual(line, f"Open Cinema is running at http://127.0.0.1:{port} (ComfyUI at {comfy})")
            finally:
                proc.kill()
                proc.wait()
                proc.stdout.close()


if __name__ == "__main__":
    unittest.main()
