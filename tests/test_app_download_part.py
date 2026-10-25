import tempfile
import unittest
from pathlib import Path

from app.comfy import download_output
from app.outage import OutageGuard

DATA = b"0123456789"


class HalfThenWholeOutput:
    node_id = "2"
    name = "x.mp4"

    def __init__(self):
        self.calls = 0

    def to_file(self, path):
        self.calls += 1
        if self.calls == 1:
            Path(path).write_bytes(DATA[:5])
            raise ConnectionError("dropped")
        Path(path).write_bytes(DATA)
        return path


class Job:
    def __init__(self, outputs):
        self.outputs = outputs


class DownloadPartTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dest = Path(tmp.name)

    def test_failure_leaves_no_final_file_and_no_part(self):
        out = HalfThenWholeOutput()
        guard = OutageGuard(window=0, sleep=lambda s: None)
        with self.assertRaises(Exception):
            download_output(Job([out]), "2", self.dest, "clip", guard)
        self.assertFalse((self.dest / "clip.mp4").exists())
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_retry_gives_complete_file_and_no_part(self):
        out = HalfThenWholeOutput()
        guard = OutageGuard(sleep=lambda s: None)
        path = download_output(Job([out]), "2", self.dest, "clip", guard)
        self.assertEqual(out.calls, 2)
        self.assertEqual(path, self.dest / "clip.mp4")
        self.assertEqual(path.read_bytes(), DATA)
        self.assertEqual([p.name for p in self.dest.iterdir()], ["clip.mp4"])
