import unittest

from open_optics.anamorphic import (
    bokeh_aspect,
    delivered_aspect_ratio,
    desqueeze_size,
)


class TestDesqueezeSize(unittest.TestCase):
    def test_widen(self):
        w, h = desqueeze_size(1280, 720, 2.0)
        self.assertAlmostEqual(w, 2560, places=6)
        self.assertAlmostEqual(h, 720, places=6)

    def test_shorten(self):
        w, h = desqueeze_size(1280, 720, 2.0, mode="shorten")
        self.assertAlmostEqual(w, 1280, places=6)
        self.assertAlmostEqual(h, 360, places=6)

    def test_133_squeeze(self):
        # 1920 * 1.33 = 2553.6
        w, _ = desqueeze_size(1920, 1080, 1.33)
        self.assertAlmostEqual(w, 2553.6, places=6)

    def test_zero_squeeze_raises(self):
        with self.assertRaises(ValueError):
            desqueeze_size(1280, 720, 0)

    def test_negative_squeeze_raises(self):
        with self.assertRaises(ValueError):
            desqueeze_size(1280, 720, -1)

    def test_bad_mode_raises(self):
        with self.assertRaises(ValueError):
            desqueeze_size(1280, 720, 2.0, mode="stretch")


class TestDeliveredAspectRatio(unittest.TestCase):
    def test_133_gate_2x(self):
        # 1.33 / 1.0 * 2.0 = 2.66
        self.assertAlmostEqual(delivered_aspect_ratio(1.33, 1.0, 2.0), 2.66, places=6)

    def test_zero_squeeze_raises(self):
        with self.assertRaises(ValueError):
            delivered_aspect_ratio(1.33, 1.0, 0)


class TestBokehAspect(unittest.TestCase):
    def test_2x_desqueezed(self):
        self.assertEqual(bokeh_aspect(2.0), 2.0)

    def test_spherical_is_round(self):
        self.assertEqual(bokeh_aspect(1.0), 1.0)

    def test_squeezed_recording_is_round(self):
        self.assertEqual(bokeh_aspect(2.0, desqueezed=False), 1.0)

    def test_zero_squeeze_raises(self):
        with self.assertRaises(ValueError):
            bokeh_aspect(0)


if __name__ == "__main__":
    unittest.main()
