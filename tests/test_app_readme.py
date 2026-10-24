"""Checks that README.md has a complete "Run the director app" section."""

import re
import unittest
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def _section() -> str:
    """Return the README text under the 'Run the director app' heading, up to the next heading of the same or higher level."""
    lines = README.read_text(encoding="utf-8").splitlines()
    start = level = None
    for i, line in enumerate(lines):
        m = re.match(r"^(#{2,3}) (.*)", line)
        if m and "Run the director app" in m.group(2):
            start, level = i, len(m.group(1))
            break
    if start is None:
        raise AssertionError("no heading containing 'Run the director app'")
    out = []
    in_fence = False
    for line in lines[start + 1:]:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = re.match(r"^(#+) ", line)
        if not in_fence and m and len(m.group(1)) <= level:
            break
        out.append(line)
    return "\n".join(out)


class ReadmeAppSectionTest(unittest.TestCase):
    def test_seven_numbered_steps(self):
        numbers = [int(m.group(1)) for m in re.finditer(r"^(\d+)\. ", _section(), re.M)]
        self.assertGreaterEqual(len(numbers), 7)
        self.assertEqual(numbers[:7], [1, 2, 3, 4, 5, 6, 7])

    def test_start_command_in_code_block(self):
        blocks = re.findall(r"```[^\n]*\n(.*?)```", _section(), re.S)
        self.assertTrue(any("python -m app" in b for b in blocks))

    def test_no_todo(self):
        self.assertNotIn("TODO", _section())


if __name__ == "__main__":
    unittest.main()
