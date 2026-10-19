import os
import tempfile
import unittest

from tests.bench_util import record_comparison, record_result

HEADER = (
    "# Node speed\n"
    "\n"
    "| node | frames | size | device | chunk_frames | seconds | peak GPU memory (GiB) |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
)
ROW_A = "| OpenOptics_A | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |\n"
ROW_B = "| OpenOptics_B | 121 | 1280x704 | cuda | 8 | not yet measured | not yet measured |\n"
TAIL = "\nend of table\n"


class RecordResultTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        self.addCleanup(os.remove, self.path)
        self.original = HEADER + ROW_A + ROW_B + TAIL
        with open(self.path, "w", encoding="utf-8", newline="") as f:
            f.write(self.original)

    def read(self):
        with open(self.path, "r", encoding="utf-8", newline="") as f:
            return f.read()

    def test_rewrites_matching_row_with_rounding(self):
        record_result("OpenOptics_A", 4, 12.34, 3.456, path=self.path)
        expected_row = "| OpenOptics_A | 121 | 1280x704 | cuda | 4 | 12.3 | 3.46 |\n"
        self.assertIn(expected_row, self.read())

    def test_other_lines_unchanged(self):
        record_result("OpenOptics_A", 4, 12.34, 3.456, path=self.path)
        new_lines = self.read().splitlines(keepends=True)
        old_lines = self.original.splitlines(keepends=True)
        self.assertEqual(len(new_lines), len(old_lines))
        for new, old in zip(new_lines, old_lines):
            if not old.startswith("| OpenOptics_A |"):
                self.assertEqual(new, old)

    def test_missing_key_leaves_file_identical(self):
        with open(self.path, "rb") as f:
            before = f.read()
        record_result("OpenOptics_Missing", 4, 12.34, 3.456, path=self.path)
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), before)


class RecordComparisonTest(unittest.TestCase):
    HEADING = "## Compared with video generation"

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        self.addCleanup(os.remove, self.path)

    def write(self, text):
        with open(self.path, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def read(self):
        with open(self.path, "r", encoding="utf-8", newline="") as f:
            return f.read()

    def test_comparison_appends_section(self):
        original = HEADER + ROW_A + TAIL
        self.write(original)
        record_comparison(14.14, path=self.path)
        text = self.read()
        self.assertTrue(text.startswith(original))
        self.assertEqual(text.count(self.HEADING), 1)
        self.assertIn("took 14.1 s", text)
        self.assertIn("took 70.7 s", text)
        self.assertIn("costs 20.0%", text)

    def test_comparison_replaces_section(self):
        before = HEADER + ROW_A + TAIL + "\n"
        self.write(before + self.HEADING + "\n\nOLD SENTENCE\nmore old text\n")
        record_comparison(14.14, path=self.path)
        text = self.read()
        self.assertTrue(text.startswith(before))
        self.assertNotIn("OLD SENTENCE", text)
        self.assertNotIn("more old text", text)
        self.assertEqual(text.count(self.HEADING), 1)
        self.assertIn("took 14.1 s", text)
        self.assertIn("costs 20.0%", text)


if __name__ == "__main__":
    unittest.main()
