import unittest

from app import progress


class ProgressTests(unittest.TestCase):
    def test_generation(self):
        self.assertAlmostEqual(progress.generation_progress(0.5), 0.425, places=9)
        self.assertAlmostEqual(progress.generation_progress(2), 0.85, places=9)
        self.assertEqual(progress.generation_progress(-1), 0)

    def test_optics(self):
        self.assertAlmostEqual(progress.optics_progress(0.5), 0.925, places=9)
        self.assertAlmostEqual(progress.optics_progress(0.5, first_run=False), 0.5, places=9)
        self.assertAlmostEqual(progress.optics_progress(5), 1.0, places=9)

    def test_monotonic(self):
        self.assertEqual(progress.monotonic(0.4, 0.2), 0.4)
        self.assertEqual(progress.monotonic(0.4, 0.6), 0.6)

    def test_messages(self):
        m = progress.message_for_node
        self.assertEqual(m("generate", "KSampler", 3, 20), "Generating video: step 3 of 20")
        self.assertEqual(m("generate", "KSampler"), "Generating video")
        self.assertEqual(m("optics", "DA3Estimate"), "Estimating depth")
        self.assertEqual(m("optics", "OpenOptics_DepthOfField"), "Applying depth of field")
        self.assertEqual(m("optics", "SaveVideo"), "Applying depth of field")
        self.assertEqual(m("optics", "Other"), "Waiting for ComfyUI")


if __name__ == "__main__":
    unittest.main()
