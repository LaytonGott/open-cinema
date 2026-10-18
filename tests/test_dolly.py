import unittest

from open_optics.dolly import dolly_zoom_focal, dolly_zoom_path


class TestDollyZoom(unittest.TestCase):
    def test_closer_halves_focal(self):
        # 35 * 2 / 4 = 17.5
        self.assertAlmostEqual(dolly_zoom_focal(35, 4, 2), 17.5, places=9)

    def test_farther_doubles_focal(self):
        # 35 * 8 / 4 = 70
        self.assertAlmostEqual(dolly_zoom_focal(35, 4, 8), 70.0, places=9)

    def test_path_keeps_subject_size(self):
        distances = [4, 3.5, 3, 2.5, 2, 1]
        path = dolly_zoom_path(35, 4, distances)
        self.assertEqual(len(path), len(distances))
        for focal, d in zip(path, distances):
            # focal / distance stays at 35 / 4 (the task's focal*distance
            # form is not constant, so the ratio form is used)
            self.assertAlmostEqual(focal * 4 / (35 * d), 1.0, places=9)

    def test_invalid_values_raise(self):
        for args in [(35, 4, 0), (35, 4, -1), (0, 4, 2), (-35, 4, 2)]:
            with self.assertRaises(ValueError):
                dolly_zoom_focal(*args)

    def test_empty_path(self):
        self.assertEqual(dolly_zoom_path(35, 4, []), [])


if __name__ == "__main__":
    unittest.main()
