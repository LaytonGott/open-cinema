import os
import tempfile
import unittest

from tests.bench_util import record_comparison, record_real_clip, record_result

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
        record_comparison(12.0, 60.0, path=self.path)
        text = self.read()
        self.assertTrue(text.startswith(original))
        self.assertEqual(text.count(self.HEADING), 1)
        self.assertIn("12.0 s", text)
        self.assertIn("60.0 s", text)
        self.assertIn("20.0%", text)

    def test_comparison_replaces_section(self):
        original = HEADER + ROW_A + TAIL
        self.write(original)
        record_comparison(12.0, 60.0, path=self.path)
        record_comparison(15.0, 50.0, path=self.path)
        text = self.read()
        self.assertTrue(text.startswith(original))
        self.assertEqual(text.count(self.HEADING), 1)
        self.assertNotIn("12.0 s", text)
        self.assertNotIn("20.0%", text)
        self.assertIn("15.0 s", text)
        self.assertIn("50.0 s", text)
        self.assertIn("30.0%", text)


class RecordRealClipTest(unittest.TestCase):
    HEADING = "## Real clip"
    COMPARISON = "## Compared with video generation"

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

    def test_record_real_clip_inserts_before_comparison(self):
        before = HEADER + ROW_A + TAIL + "\n"
        after = self.COMPARISON + "\n\nold text\n"
        self.write(before + after)
        record_real_clip(1.0, 2.0, 3.0, 4, 5.0, path=self.path)
        text = self.read()
        self.assertTrue(text.startswith(before))
        self.assertTrue(text.endswith(after))
        self.assertEqual(text.count(self.HEADING), 1)
        self.assertLess(text.index(self.HEADING), text.index(self.COMPARISON))

    def test_record_real_clip_replaces_section(self):
        original = HEADER + ROW_A + TAIL + "\n" + self.COMPARISON + "\n\nold\n"
        self.write(original)
        record_real_clip(1.0, 2.0, 3.0, 4, 5.0, path=self.path)
        record_real_clip(7.0, 8.0, 9.0, 6, 1.5, path=self.path)
        text = self.read()
        self.assertEqual(text.count(self.HEADING), 1)
        self.assertIn("| Depth to Metric (s) | 7.0 |", text)
        self.assertIn("| Peak GPU memory (GiB) | 1.50 |", text)
        self.assertNotIn("| Depth to Metric (s) | 1.0 |", text)
        self.assertNotIn("5.00", text)
        self.assertTrue(text.startswith(HEADER + ROW_A + TAIL + "\n"))
        self.assertTrue(text.endswith(self.COMPARISON + "\n\nold\n"))

    def test_record_comparison_keeps_real_clip_section(self):
        self.write(HEADER + ROW_A + TAIL)
        record_real_clip(1.0, 2.0, 3.0, 4, 5.0, path=self.path)
        record_comparison(12.0, 60.0, path=self.path)
        text = self.read()
        self.assertEqual(text.count(self.HEADING), 1)
        self.assertIn("| Depth to Metric (s) | 1.0 |", text)
        self.assertEqual(text.count(self.COMPARISON), 1)

    def test_real_clip_section_has_no_node_rows(self):
        self.write(HEADER + ROW_A + TAIL)
        record_real_clip(1.0, 2.0, 3.0, 4, 5.0, path=self.path)
        lines = self.read().splitlines()
        start = lines.index(self.HEADING)
        section = lines[start:]
        self.assertGreater(len(section), 1)
        for line in section:
            self.assertFalse(line.startswith("| OpenOptics_"))


if __name__ == "__main__":
    unittest.main()
