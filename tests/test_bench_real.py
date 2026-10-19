"""Real-clip benchmark skeleton: skipped unless the benchmark fixture and CUDA are present."""
import os
import re
import tempfile
import unittest

import torch

DEFAULT_FIXTURE_DIR = r"D:\OpenCinema\fixtures\real_clip"
FIXTURE_FILES = ("frames_u8.npy", "depth_u8.npy", "subject_mask_u8.npy")


def missing_reason(fixture_dir=None):
    """Return None if the real-clip fixture and CUDA are available, else a string saying what is missing.

    fixture_dir is a folder path; default is OPEN_OPTICS_FIXTURE_DIR (read on each call), else
    D:\\OpenCinema\\fixtures\\real_clip. Only reads; never copies or writes the fixture.
    """
    if fixture_dir is None:
        fixture_dir = os.environ.get("OPEN_OPTICS_FIXTURE_DIR", DEFAULT_FIXTURE_DIR)
    missing = [n for n in FIXTURE_FILES if not os.path.isfile(os.path.join(fixture_dir, n))]
    if missing:
        return (f"real clip fixture folder {fixture_dir} is missing {', '.join(missing)}; "
                "set OPEN_OPTICS_FIXTURE_DIR to the folder that holds them")
    if not torch.cuda.is_available():
        return "CUDA is not available"
    return None


def parse_layers(message):
    """Return the integer after ' layers=' in an open_optics_nodes log message (a count, unitless).

    Raises ValueError if the message has no ' layers=<n>' field.
    """
    match = re.search(r" layers=(\d+)", message)
    if match is None:
        raise ValueError(f"no layers= field in log message: {message!r}")
    return int(match.group(1))


@unittest.skipUnless(os.environ.get("OPEN_OPTICS_BENCH") == "1", "set by npm run test:bench")
class TestBenchReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reason = missing_reason()
        if reason is not None:
            raise unittest.SkipTest(reason)

    def test_bench_real_clip(self):
        pass


class TestMissingReason(unittest.TestCase):
    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            reason = missing_reason(d)
        self.assertIn("frames_u8.npy", reason)
        self.assertIn(d, reason)
        self.assertIn("OPEN_OPTICS_FIXTURE_DIR", reason)

    def test_all_files_present(self):
        with tempfile.TemporaryDirectory() as d:
            for n in FIXTURE_FILES:
                open(os.path.join(d, n), "wb").close()
            reason = missing_reason(d)
        self.assertTrue(reason is None or "CUDA" in reason)


class TestParseLayers(unittest.TestCase):
    def test_parse_layers_known_line(self):
        line = ("node=OpenOptics_DepthOfField device=cuda:0 frames=2 chunk_frames=2 "
                "seconds=1.234 layers=7")
        self.assertEqual(parse_layers(line), 7)

    def test_parse_layers_missing(self):
        line = "node=OpenOptics_DepthOfField device=cuda:0 frames=2 chunk_frames=2 seconds=1.234"
        with self.assertRaises(ValueError):
            parse_layers(line)


if __name__ == "__main__":
    unittest.main()
