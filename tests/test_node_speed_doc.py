"""docs/node-speed.md has the header line and exactly one row for each of the eight nodes."""
import os
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


def split_row(line):
    """Split a table row on '|' and return the stripped cells, without the outer empty ones."""
    cells = [cell.strip() for cell in line.split("|")]
    return cells[1:-1]


def is_float(text):
    """Return True when text parses as a float, else False."""
    try:
        float(text)
    except ValueError:
        return False
    return True


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

    def test_node_speed_doc_has_rows(self):
        """Each node row has 7 cells with the expected frames, size and device."""
        for key in KEYS:
            row = [line for line in self.lines if line.startswith("| %s |" % key)][0]
            cells = split_row(row)
            self.assertEqual(len(cells), 7, key)
            self.assertEqual(cells[1], "121", key)
            self.assertEqual(cells[2], "1280x704", key)
            self.assertEqual(cells[3], "cuda", key)
        self.assertIn("## Compared with video generation", self.lines)
        self.assertEqual(len(split_row(HEADER)), 7)
        self.assertTrue(is_float("1.5"))
        self.assertFalse(is_float("not yet measured"))

    @unittest.skipUnless(os.environ.get("OPEN_OPTICS_BENCH") == "1", "set by npm run test:bench")
    def test_node_speed_doc_has_numbers(self):
        """Every row has measured seconds and peak GiB numbers."""
        self.assertNotIn("not yet measured", "\n".join(self.lines))
        for key in KEYS:
            row = [line for line in self.lines if line.startswith("| %s |" % key)][0]
            cells = split_row(row)
            self.assertTrue(is_float(cells[5]), key)
            self.assertTrue(is_float(cells[6]), key)


if __name__ == "__main__":
    unittest.main()
