import signal
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

    def test_clean_shutdown(self):
        port = _free_port()
        comfy = f"http://127.0.0.1:{_free_port()}"
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.Popen(
                [sys.executable, "-m", "app", "--port", str(port), "--data-dir", tmp, "--comfyui", comfy],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=flags,
            )
            try:
                proc.stdout.readline()
                if sys.platform == "win32":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.send_signal(signal.SIGTERM)
                _, err = proc.communicate(timeout=10)
                self.assertEqual(proc.returncode, 0)
                self.assertNotIn("Traceback", err)
            finally:
                proc.kill()
                proc.wait()

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
