import inspect
import os
import unittest

from open_optics.framing import (
    sensor_height_mm, subject_distance_m, subject_height_px,
)


class TestFraming(unittest.TestCase):
    def test_sensor_height_mm_known_value(self):
        # 36 mm * 704 / 1280 = 19.8 mm
        self.assertAlmostEqual(sensor_height_mm(36.0, 1280, 704), 19.8, places=6)

    def test_sensor_height_mm_rejects_zero_width(self):
        with self.assertRaisesRegex(ValueError, "image_width_px"):
            sensor_height_mm(36.0, 0, 704)

    def test_subject_distance_m_known_value(self):
        # h = 24 * 600 / 1200 = 12 mm; u = 50 * (1 + 1700 / 12) / 1000
        self.assertAlmostEqual(subject_distance_m(50, 24, 600, 1200), 7.133333, places=6)

    def test_subject_distance_m_keyword_arguments(self):
        value = subject_distance_m(
            focal_mm=50, sensor_height_mm=24, subject_height_px=600,
            image_height_px=1200, real_height_m=1.7,
        )
        self.assertAlmostEqual(value, 7.133333, places=6)

    def test_subject_distance_m_hand_values(self):
        cases = [
            ((50, 24, 600, 1200), 7.133333333),
            ((50, 19.8, 422.4, 704), 7.204882155),
            ((24, 19.8, 422.4, 704), 3.458343434),
            ((50, 24, 1200, 1200), 3.591666667),
        ]
        for args, expected in cases:
            with self.subTest(args=args):
                self.assertAlmostEqual(subject_distance_m(*args), expected, places=6)

    def test_subject_distance_m_custom_real_height(self):
        cases = [
            ((85, 24, 600, 1200, 0.3), 2.21),
            ((50, 19.8, 422.4, 704, 1.65), 6.994444444),
            ((50, 24, 300, 1200), 14.216666667),
            ((100, 24, 300, 1200), 28.433333333),
        ]
        for args, expected in cases:
            with self.subTest(args=args):
                self.assertAlmostEqual(subject_distance_m(*args), expected, places=6)

    def test_subject_distance_m_double_lens_double_distance(self):
        self.assertAlmostEqual(subject_distance_m(100, 24, 300, 1200),
                               2 * subject_distance_m(50, 24, 300, 1200), places=6)

    def test_subject_distance_m_keywords_match_positional_and_default(self):
        keyword = subject_distance_m(focal_mm=50, sensor_height_mm=24,
                                     subject_height_px=600, image_height_px=1200)
        self.assertAlmostEqual(keyword, subject_distance_m(50, 24, 600, 1200), places=6)
        self.assertAlmostEqual(keyword, subject_distance_m(
            focal_mm=50, sensor_height_mm=24, subject_height_px=600,
            image_height_px=1200, real_height_m=1.7), places=6)
        self.assertAlmostEqual(keyword, 7.133333, places=6)

    def test_subject_distance_m_default_real_height(self):
        self.assertEqual(subject_distance_m(50, 24, 600, 1200),
                         subject_distance_m(50, 24, 600, 1200, 1.7))

    def test_subject_height_px_known_value(self):
        # h = 35 * 1700 / (5000 - 35) mm; * 704 / 24
        self.assertAlmostEqual(subject_height_px(35, 24, 704, 5.0), 351.527358, places=6)

    def test_subject_height_px_hand_values(self):
        # h = 85*300/(2210-85) = 12 mm on a 24 mm sensor, 1200 px -> 600 px
        self.assertAlmostEqual(subject_height_px(85, 24, 1200, 2.21, 0.3), 600, places=6)
        self.assertAlmostEqual(subject_height_px(50, 19.8, 704, 7.204882155), 422.4, delta=1e-5)
        self.assertEqual(
            subject_height_px(35, 24, 704, 5.0),
            subject_height_px(focal_mm=35, sensor_height_mm=24, image_height_px=704,
                              distance_m=5.0, real_height_m=1.7))

    def test_subject_height_px_round_trip(self):
        distance = subject_distance_m(50, 24, 333, 1080, 1.7)
        self.assertAlmostEqual(
            subject_height_px(50, 24, 1080, distance, 1.7), 333, places=6)

    def test_subject_height_px_rejects_close_distance(self):
        with self.assertRaisesRegex(ValueError, "distance_m"):
            subject_height_px(50, 24, 1080, 0.05)
        with self.assertRaisesRegex(ValueError, "distance_m"):
            subject_height_px(50, 24, 1080, 0)

    def test_sensor_height_mm_rejects_bad_arguments(self):
        good = dict(sensor_width_mm=36.0, image_width_px=1280,
                    image_height_px=704)
        for name in good:
            for bad in (0, -1, float('nan'), float('inf'), 'abc', True):
                with self.subTest(name=name, bad=bad):
                    kwargs = dict(good, **{name: bad})
                    with self.assertRaisesRegex(ValueError, name):
                        sensor_height_mm(**kwargs)

    def test_subject_height_px_rejects_bad_arguments(self):
        good = dict(focal_mm=50, sensor_height_mm=24, image_height_px=1080,
                    distance_m=5.0, real_height_m=1.7)
        for name in good:
            for bad in (0, -1, float('nan'), float('inf'), 'abc', True):
                with self.subTest(name=name, bad=bad):
                    kwargs = dict(good, **{name: bad})
                    with self.assertRaisesRegex(ValueError, name):
                        subject_height_px(**kwargs)

    def test_subject_distance_m_rejects_bad_arguments(self):
        good = dict(focal_mm=50, sensor_height_mm=24, subject_height_px=600,
                    image_height_px=1200, real_height_m=1.7)
        for name in good:
            for bad in (0, -1, float("nan"), float("inf"), "abc", True):
                with self.subTest(name=name, bad=bad):
                    kwargs = dict(good, **{name: bad})
                    with self.assertRaisesRegex(ValueError, name):
                        subject_distance_m(**kwargs)

    def test_subject_distance_m_accepts_ints(self):
        self.assertIsInstance(subject_distance_m(50, 24, 600, 1200), float)

    def test_readme_documents_helpers(self):
        path = os.path.join(os.path.dirname(__file__), "..", "README.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("## Helpers", text)
        self.assertIn("7.1", text)

    def test_docstrings_state_units_and_estimate(self):
        for func in (subject_distance_m, subject_height_px):
            doc = inspect.getdoc(func).lower()
            for word in ("millimetre", "metre", "pixel", "thin-lens",
                         "estimate"):
                self.assertIn(word, doc, f"{func.__name__}: {word}")
        doc = inspect.getdoc(sensor_height_mm).lower()
        for word in ("millimetre", "pixel"):
            self.assertIn(word, doc)


if __name__ == "__main__":
    unittest.main()
