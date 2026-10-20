import json
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

from tests.app_harness import SHOT
from tests.fake_comfy import FakeComfy

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

    def test_shutdown_releases_ports_and_keeps_job(self):
        port, proxy_port = _free_port(), _free_port()
        fake = FakeComfy()
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        proc = None
        with tempfile.TemporaryDirectory() as tmp:
            try:
                comfy = fake.start()
                fake.hold_at("SamplerCustomAdvanced")
                proc = subprocess.Popen(
                    [sys.executable, "-m", "app", "--port", str(port), "--proxy-port", str(proxy_port),
                     "--data-dir", tmp, "--comfyui", comfy],
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=flags,
                )
                proc.stdout.readline()
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/shots",
                    data=json.dumps(SHOT).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    self.assertEqual(response.status, 201)
                deadline = time.time() + 20
                while fake._running is None and time.time() < deadline:
                    time.sleep(0.05)
                self.assertIsNotNone(fake._running, "the fake never started a job")
                if sys.platform == "win32":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.send_signal(signal.SIGTERM)
                _, err = proc.communicate(timeout=10)
                self.assertEqual(proc.returncode, 0)
                self.assertNotIn("Traceback", err)
                for bound in (port, proxy_port):
                    with socket.socket() as s:
                        s.bind(("127.0.0.1", bound))
                self.assertEqual(fake._interrupt, set())
            finally:
                fake.release()
                if proc is not None:
                    proc.kill()
                    proc.wait()
                fake.stop()

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
