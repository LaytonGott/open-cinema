"""Tests for app.shot: the option lists and the subject height table."""

import unittest

from app import shot


class OptionListTests(unittest.TestCase):
    def test_cameras(self):
        self.assertEqual(shot.CAMERAS, [
            {"id": "static", "label": "Static"},
            {"id": "dolly-in", "label": "Dolly in"},
            {"id": "dolly-out", "label": "Dolly out"},
            {"id": "pan-left", "label": "Pan left"},
            {"id": "pan-right", "label": "Pan right"},
            {"id": "tilt-up", "label": "Tilt up"},
            {"id": "orbit", "label": "Orbit"},
            {"id": "handheld", "label": "Handheld"},
        ])

    def test_framings(self):
        self.assertEqual(shot.FRAMINGS, [
            {"id": "close-up", "label": "Close-up"},
            {"id": "waist-up", "label": "Waist-up"},
            {"id": "full-body", "label": "Full body"},
            {"id": "wide", "label": "Wide"},
        ])

    def test_lenses(self):
        self.assertEqual(shot.LENSES, [24, 35, 50, 85])

    def test_apertures(self):
        self.assertEqual(shot.APERTURES, [1.4, 2, 2.8, 4, 5.6, 8, 11, 16])

    def test_subject_height_fraction(self):
        self.assertEqual(
            shot.SUBJECT_HEIGHT_FRACTION,
            {"close-up": 2.8, "waist-up": 1.6, "full-body": 0.85, "wide": 0.35},
        )


if __name__ == "__main__":
    unittest.main()
