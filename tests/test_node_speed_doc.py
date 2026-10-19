"""docs/node-speed.md has the header line and exactly one row for each of the eight nodes."""
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "docs" / "node-speed.md"
HEADER = "| node | frames | size | device | chunk_frames | seconds | peak GPU memory (GiB) |"
KEYS = [
    "OpenOptics_Anamorphic",
    "OpenOptics_ChromaticAberration",
    "OpenOptics_DepthOfField",
    "OpenOptics_DepthTemporalSmooth",
    "OpenOptics_DepthToMetric",
    "OpenOptics_FocalCrop",
    "OpenOptics_LensDistortion",
    "OpenOptics_Vignette",
]


class NodeSpeedDocTest(unittest.TestCase):
    def setUp(self):
        self.lines = DOC.read_text(encoding="utf-8").splitlines()

    def test_header_line(self):
        self.assertIn(HEADER, self.lines)

    def test_one_row_per_node(self):
        for key in KEYS:
            rows = [line for line in self.lines if line.startswith("| %s |" % key)]
            self.assertEqual(len(rows), 1, key)

    def test_no_other_node_rows(self):
        rows = [line for line in self.lines if line.startswith("| OpenOptics_")]
        self.assertEqual(len(rows), len(KEYS))


if __name__ == "__main__":
    unittest.main()
