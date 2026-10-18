"""Tests that the distortion docstrings use the agreed coordinate wording."""
import unittest

from open_optics import distortion

PHRASE = "normalised image-plane coordinates (x/z, y/z)"
FUNCS = (
    "distort_point",
    "undistort_point",
    "distort_point_opencv",
    "undistort_point_opencv",
    "straight_line_deviation",
)


def _flat(text):
    return " ".join(text.split())


class TestDistortionDocs(unittest.TestCase):
    def test_no_frame_fraction_wording(self):
        with open(distortion.__file__, encoding="utf-8") as f:
            source = f.read().lower()
        self.assertNotIn("frame-fraction", source)
        self.assertNotIn("frame fraction", source)

    def test_docstrings_state_coordinate_convention(self):
        self.assertIn(PHRASE, _flat(distortion.__doc__))
        for name in FUNCS:
            with self.subTest(function=name):
                doc = getattr(distortion, name).__doc__
                self.assertIn(PHRASE, _flat(doc))

    def test_point_docstrings_state_coefficient_orders(self):
        for name in ("distort_point", "undistort_point"):
            doc = _flat(getattr(distortion, name).__doc__)
            for text in ("(k1, k2, k3, p1, p2)", "(k1, k2, p1, p2, k3)",
                         "opencv_to_library_coeffs"):
                with self.subTest(function=name, text=text):
                    self.assertIn(text, doc)


if __name__ == "__main__":
    unittest.main()
