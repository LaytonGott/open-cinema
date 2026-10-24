"""Start the Open Cinema app against the fake ComfyUI server, for backend and browser tests.

    from tests.app_harness import AppHarness

    with AppHarness() as h:
        h.url            # "http://127.0.0.1:<port>", the app
        h.fake           # the FakeComfy (tests/fake_comfy.py): h.fake.fail(...), h.fake.stop(), h.fake.executed ...
        h.get("/api/health")                        # -> (status, json)
        h.post("/api/shots", {"description": ...})  # -> (status, json)
        h.wait_for_shot(shot_id, "done")            # -> the record, raises AssertionError on timeout or a different final state
        h.restart_app()                             # stop and start the app process again on the same data dir and port

The app runs as `python -m app --comfyui <fake url> --port <free port> --data-dir <temp dir>` in the project's Python
(sys.executable), exactly as a user starts it. This file is a test fixture: do not edit it to make a test pass.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from tests.fake_comfy import FakeComfy

ROOT = Path(__file__).resolve().parent.parent
TERMINAL = ("done", "failed", "cancelled")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class AppHarness:
    def __init__(self, fake=None, delay=0.03, extra_args=()):
        self.fake = fake or FakeComfy(delay=delay)
        self._own_fake = fake is None
        self.data_dir = Path(tempfile.mkdtemp(prefix="opencinema_data_"))
        self.port = free_port()
        self.extra_args = list(extra_args)
        self._proc: subprocess.Popen | None = None
        fd, name = tempfile.mkstemp(prefix="opencinema_app_", suffix=".log")
        os.close(fd)
        self._log = Path(name)
        self._logfile = None

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    # ------------------------------------------------------------ lifecycle
    def start(self, timeout=60):
        """Start the fake ComfyUI (if it is not running) and the app. A port picked a moment ago may have been taken by a
        parallel test process before the app bound it, and a loaded machine starts slowly: try again on a new port."""
        if self.fake._thread is None:
            self.fake.start()
        for attempt in range(3):
            try:
                self.start_app(timeout)
                return self
            except RuntimeError:
                self.stop_app()
                if attempt == 2:
                    raise
                self.port = free_port()
        return self

    def start_app(self, timeout=40):
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        env.pop("COMFY_BASE_URL", None)
        args = [sys.executable, "-m", "app", "--comfyui", self.fake.url, "--port", str(self.port), "--data-dir", str(self.data_dir), *self.extra_args]
        self._logfile = logfile = open(self._log, "ab")
        self._proc = subprocess.Popen(args, cwd=str(ROOT), env=env, stdout=logfile, stderr=subprocess.STDOUT)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError(f"the app exited with code {self._proc.returncode} while starting:\n{self.log()}")
            try:
                status, _ = self.get("/api/health", timeout=5)
                if status == 200:
                    return
            except Exception:
                pass
            time.sleep(0.15)
        self.stop_app()
        raise RuntimeError(f"the app did not answer on {self.url} within {timeout} s:\n{self.log()}")

    def stop_app(self):
        proc, self._proc = self._proc, None
        if proc is None:
            return
        self._close_log()
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(10)

    def _close_log(self):
        if self._logfile is not None:
            try:
                self._logfile.close()
            except OSError:
                pass
            self._logfile = None

    def restart_app(self):
        self.stop_app()
        self.start_app()

    def stop(self):
        self.stop_app()
        if self._own_fake:
            self.fake.close()
        shutil.rmtree(self.data_dir, ignore_errors=True)
        try:
            self._log.unlink()
        except OSError:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    def log(self):
        try:
            return self._log.read_text(encoding="utf-8", errors="replace")[-4000:]
        except OSError:
            return ""

    # ------------------------------------------------------------ HTTP helpers (standard library)
    def request(self, method, path, body=None, timeout=15):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data, method=method, headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        try:
            return status, (json.loads(raw) if raw else None)
        except ValueError:
            return status, raw

    def get(self, path, timeout=15):
        return self.request("GET", path, timeout=timeout)

    def post(self, path, body=None, timeout=15):
        return self.request("POST", path, {} if body is None else body, timeout=timeout)

    def reset(self, timeout=30):
        """Start a test from a clean slate: release the fake, wait until no shot is running, delete every shot, clear ComfyUI's cache.

        A harness shared by the tests of a class keeps its shots, and a page restores the latest one on load, so a test that
        generates its own shot must call this first or it may see the shot an earlier test left behind.
        """
        self.fake.release()
        deadline = time.time() + timeout
        while time.time() < deadline:
            code, body = self.get("/api/shots")
            if code == 200 and all(s["status"] in TERMINAL for s in body["shots"]):
                break
            time.sleep(0.1)
        else:
            raise AssertionError("a shot was still running; cannot reset")
        for shot in body["shots"]:
            self.request("DELETE", f"/api/shots/{shot['id']}")
        self.fake.reset_cache()

    def wait_for_shot(self, shot_id, status="done", timeout=60):
        """Poll the shot until it reaches a final state. Returns the record if it is `status`; raises AssertionError otherwise."""
        deadline = time.time() + timeout
        record = None
        while time.time() < deadline:
            code, record = self.get(f"/api/shots/{shot_id}")
            if code == 200 and record["status"] in TERMINAL:
                break
            time.sleep(0.1)
        else:
            raise AssertionError(f"shot {shot_id} did not finish within {timeout} s; last record: {record}")
        if record["status"] != status:
            raise AssertionError(f"shot {shot_id} ended {record['status']!r}, wanted {status!r}: error={record.get('error')} message={record.get('message')}")
        return record

    def wait_until(self, shot_id, predicate, timeout=30, what="the condition"):
        deadline = time.time() + timeout
        record = None
        while time.time() < deadline:
            code, record = self.get(f"/api/shots/{shot_id}")
            if code == 200 and predicate(record):
                return record
            time.sleep(0.05)
        raise AssertionError(f"{what} did not hold within {timeout} s; last record: {record}")


SHOT = {"description": "A woman in a red coat crosses a rainy cobblestone street at night.", "camera": "dolly-in", "lens_mm": 50, "aperture": 2.8, "framing": "full-body", "seed": 7}
