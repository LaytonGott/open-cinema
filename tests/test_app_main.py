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

    def test_port_in_use(self):
        comfy = f"http://127.0.0.1:{_free_port()}"
        with socket.socket() as blocker, tempfile.TemporaryDirectory() as tmp:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen()
            port = blocker.getsockname()[1]
            proc = subprocess.Popen(
                [sys.executable, "-m", "app", "--port", str(port), "--data-dir", tmp, "--comfyui", comfy],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                _, err = proc.communicate(timeout=30)
            finally:
                proc.kill()
                proc.wait()
            self.assertEqual(proc.returncode, 1)
            self.assertIn("could not start", err)
            self.assertIn(str(port), err)
            self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
