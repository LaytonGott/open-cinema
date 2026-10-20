"""Tests of `python -m app` run as a real subprocess."""

import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

OPTIONS = ["--comfyui", "--host", "--port", "--proxy-port", "--proxy-url", "--data-dir"]


def _run(args, timeout):
    """Run `python -m app <args>` at the repo root; return the CompletedProcess."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "app", *args],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    return proc.returncode, out, err


class CliProcessTests(unittest.TestCase):
    def test_help_lists_options(self):
        code, out, err = _run(["--help"], 20)
        self.assertEqual(code, 0, err)
        for option in OPTIONS:
            self.assertIn(option, out)

    def test_port_in_use(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = _run(["--port", str(port), "--data-dir", tmp], 20)
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", out + err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)


if __name__ == "__main__":
    unittest.main()
