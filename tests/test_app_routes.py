import unittest

from tests.app_harness import AppHarness
from tests.fake_comfy import FakeComfy


class OptionsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_get_options(self):
        status, body = self.harness.get("/api/options")
        self.assertEqual(status, 200)
        self.assertEqual(
            set(body), {"cameras", "lenses", "apertures", "framings", "defaults"}
        )
        self.assertEqual(len(body["cameras"]), 8)
        self.assertEqual(
            [c["id"] for c in body["cameras"]],
            ["static", "dolly-in", "dolly-out", "pan-left", "pan-right", "tilt-up", "orbit", "handheld"],
        )
        self.assertEqual(
            [c["label"] for c in body["cameras"]],
            ["Static", "Dolly in", "Dolly out", "Pan left", "Pan right", "Tilt up", "Orbit", "Handheld"],
        )
        self.assertEqual(body["lenses"], [24, 35, 50, 85])
        self.assertEqual(body["apertures"], [1.4, 2, 2.8, 4, 5.6, 8, 11, 16])
        self.assertEqual(len(body["framings"]), 4)
        self.assertEqual(
            [(f["id"], f["label"]) for f in body["framings"]],
            [("close-up", "Close-up"), ("waist-up", "Waist-up"), ("full-body", "Full body"), ("wide", "Wide")],
        )
        self.assertEqual(
            body["defaults"],
            {"camera": "static", "lens_mm": 50, "aperture": 2.8, "framing": "full-body"},
        )


if __name__ == "__main__":
    unittest.main()
