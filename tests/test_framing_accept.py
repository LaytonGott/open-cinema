"""Runs scripts/accept_framing.py and checks that it passes."""

import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FramingAcceptTest(unittest.TestCase):
    def test_framing_acceptance_script_passes(self):
        path = os.path.join(REPO_ROOT, "scripts", "accept_framing.py")
        result = subprocess.run(
            [sys.executable, path], capture_output=True, text=True, cwd=REPO_ROOT
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("framing distance: OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
