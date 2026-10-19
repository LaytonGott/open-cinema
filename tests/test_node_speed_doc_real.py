import os
import re
import unittest

DOC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "node-speed.md")


class NodeSpeedDocRealTest(unittest.TestCase):
    def test_real_clip_section_is_measured(self):
        with open(DOC, encoding="utf-8") as f:
            text = f.read()
        match = re.search(r"^## Real clip\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
        self.assertIsNotNone(match)
        self.assertNotIn("not yet measured", match.group(1))


if __name__ == "__main__":
    unittest.main()
