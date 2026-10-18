import unittest

from open_optics.anamorphic import (
    bokeh_aspect,
    delivered_aspect_ratio,
    desqueeze_point,
    desqueeze_size,
    squeeze_point,
    squeeze_size,
)


class TestPointConversion(unittest.TestCase):
    def test_desqueeze_point_widen(self):
        x, y = desqueeze_point(100, 50, 2.0, "widen")
        self.assertAlmostEqual(x, 200.0, places=9)
        self.assertAlmostEqual(y, 50.0, places=9)

    def test_desqueeze_point_shorten(self):
        x, y = desqueeze_point(100, 50, 2.0, "shorten")
        self.assertAlmostEqual(x, 100.0, places=9)
        self.assertAlmostEqual(y, 25.0, places=9)

    def test_fractional_unchanged(self):
        for mode in ("widen", "shorten"):
            self.assertEqual(
                desqueeze_point(0.25, 0.75, 2.0, mode, fractional=True),
                (0.25, 0.75),
            )
            self.assertEqual(
                squeeze_point(0.25, 0.75, 2.0, mode, fractional=True),
                (0.25, 0.75),
            )

    def test_round_trip(self):
        for mode in ("widen", "shorten"):
            sx, sy = desqueeze_point(123.5, 67.25, 1.33, mode)
            x, y = squeeze_point(sx, sy, 1.33, mode)
            self.assertAlmostEqual(x, 123.5, places=9)
            self.assertAlmostEqual(y, 67.25, places=9)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            desqueeze_point(1, 1, -1)
        with self.assertRaises(ValueError):
            squeeze_point(1, 1, -1)
        with self.assertRaises(ValueError):
            desqueeze_point(1, 1, 2.0, "bad")
        with self.assertRaises(ValueError):
            squeeze_point(float("nan"), 1, 2.0)


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


class TestSqueezeSize(unittest.TestCase):
    def test_round_trip(self):
        for mode in ("widen", "shorten"):
            for squeeze in (1.33, 1.5, 1.8, 2.0):
                with self.subTest(mode=mode, squeeze=squeeze):
                    w, h = desqueeze_size(1920, 1080, squeeze, mode=mode)
                    w, h = squeeze_size(w, h, squeeze, mode=mode)
                    self.assertAlmostEqual(w, 1920, places=9)
                    self.assertAlmostEqual(h, 1080, places=9)

    def test_rounded_round_trip_width(self):
        for squeeze in (1.33, 1.5, 1.8, 2.0):
            with self.subTest(squeeze=squeeze):
                w, h = desqueeze_size(1920, 1080, squeeze)
                w, _ = squeeze_size(round(w), round(h), squeeze)
                self.assertAlmostEqual(w, 1920, delta=1)

    def test_zero_squeeze_raises(self):
        with self.assertRaises(ValueError):
            squeeze_size(1920, 1080, 0)

    def test_bad_mode_raises(self):
        with self.assertRaises(ValueError):
            squeeze_size(1920, 1080, 2.0, mode="stretch")


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
