import unittest

import open_optics


class SmokeTest(unittest.TestCase):
    def test_package_imports(self):
        self.assertIn("lens math", open_optics.__doc__)


if __name__ == "__main__":
    unittest.main()
