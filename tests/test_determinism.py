import unittest

from open_optics import (
    Lens,
    blur_diameter_mm,
    combined_vignette,
    distort_point,
    dof_summary,
    field_of_view,
    get_sensor,
    shot_summary,
    undistort_point,
)


def _calls():
    sensor = get_sensor("full frame")
    lens = Lens(50, 2, 22)
    return {
        "fov": lambda: field_of_view(50, 36, 24),
        "blur": lambda: blur_diameter_mm(50, 2.8, 2000, 5000),
        "dof": lambda: dof_summary(50, 2.8, 3000, 0.03),
        "distort": lambda: distort_point(0.3, 0.2, k1=-0.1),
        "undistort": lambda: undistort_point(0.3, 0.2, k1=-0.1),
        "vignette": lambda: combined_vignette(50, 10, 5, 21.6, 4, 2),
        "summary": lambda: shot_summary(sensor, lens, 2.8, 3),
    }


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_equal(self):
        for name, call in _calls().items():
            with self.subTest(name=name):
                self.assertEqual(call(), call())

    def test_order_does_not_matter(self):
        calls = _calls()
        forward = {name: call() for name, call in calls.items()}
        backward = {name: calls[name]() for name in reversed(list(calls))}
        self.assertEqual(forward, backward)


if __name__ == "__main__":
    unittest.main()
