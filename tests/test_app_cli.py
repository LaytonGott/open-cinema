import contextlib
import io
import unittest
from pathlib import Path

from app.cli import parse_args

OPTIONS = ["--comfyui", "--host", "--port", "--proxy-port", "--proxy-url", "--data-dir"]


class CliTest(unittest.TestCase):
    def test_defaults(self):
        a = parse_args([])
        self.assertEqual(a.comfyui, "http://127.0.0.1:8188")
        self.assertEqual(a.host, "127.0.0.1")
        self.assertEqual(a.port, 8000)
        self.assertEqual(a.proxy_port, 0)
        self.assertIsNone(a.proxy_url)
        self.assertIsInstance(a.data_dir, Path)
        self.assertEqual(a.data_dir.name, "data")
        self.assertEqual(a.data_dir.parent.name, "app")

    def test_overrides(self):
        a = parse_args(["--comfyui", "http://x:1", "--host", "0.0.0.0", "--port", "9",
                        "--proxy-port", "10", "--proxy-url", "http://p", "--data-dir", "d"])
        self.assertEqual(a.comfyui, "http://x:1")
        self.assertEqual(a.host, "0.0.0.0")
        self.assertEqual(a.port, 9)
        self.assertEqual(a.proxy_port, 10)
        self.assertEqual(a.proxy_url, "http://p")
        self.assertEqual(a.data_dir, Path("d"))

    def test_help_lists_options(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            parse_args(["--help"])
        self.assertEqual(cm.exception.code, 0)
        for name in OPTIONS:
            self.assertIn(name, out.getvalue())

    def test_bad_port_exits_2(self):
        for argv in (["--port", "abc"], ["--port", "70000"], ["--proxy-port", "-1"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
                parse_args(argv)
            self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
