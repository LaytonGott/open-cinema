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


class EstimateValueTests(unittest.TestCase):
    FRACTIONS = {"close-up": 2.8, "waist-up": 1.6, "full-body": 0.85, "wide": 0.35}

    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_full_body_50mm(self):
        status, body = self.harness.get("/api/estimate?lens_mm=50&framing=full-body")
        self.assertEqual(status, 200)
        # (50 + 50 * 1700 / (0.85 * 19.8)) / 1000 = (50 + 85000 / 16.83) / 1000
        self.assertAlmostEqual(body["subject_distance_m"], 5.1005, places=4)
        self.assertAlmostEqual(body["sensor_height_mm"], 19.8, places=4)
        self.assertAlmostEqual(body["subject_height_fraction"], 0.85, places=4)
        self.assertAlmostEqual(body["real_height_m"], 1.7, places=4)

    def test_all_lens_framing_pairs(self):
        _, options = self.harness.get("/api/options")
        framing_ids = [f["id"] for f in options["framings"]]
        self.assertEqual(set(framing_ids), set(self.FRACTIONS))
        pairs = 0
        for lens in (24, 35, 50, 85):
            for framing in framing_ids:
                with self.subTest(lens=lens, framing=framing):
                    fraction = self.FRACTIONS[framing]
                    expected = (lens + lens * 1700 / (fraction * 19.8)) / 1000
                    status, body = self.harness.get(
                        f"/api/estimate?lens_mm={lens}&framing={framing}"
                    )
                    self.assertEqual(status, 200)
                    self.assertAlmostEqual(body["subject_distance_m"], expected, delta=0.0001)
                    self.assertAlmostEqual(body["sensor_height_mm"], 19.8, delta=0.0001)
                    self.assertAlmostEqual(body["subject_height_fraction"], fraction, delta=0.0001)
                    self.assertAlmostEqual(body["real_height_m"], 1.7, delta=0.0001)
                    pairs += 1
        self.assertEqual(pairs, 16)


class EstimateErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def check_invalid(self, query, field):
        status, body = self.harness.get("/api/estimate" + query)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_shot")
        self.assertTrue(body["error"]["message"])
        self.assertEqual(body["error"]["field"], field)

    def test_lens_not_offered(self):
        self.check_invalid("?lens_mm=30&framing=full-body", "lens_mm")

    def test_lens_not_a_number(self):
        self.check_invalid("?lens_mm=abc&framing=full-body", "lens_mm")

    def test_lens_missing(self):
        self.check_invalid("?framing=full-body", "lens_mm")

    def test_framing_unknown(self):
        self.check_invalid("?lens_mm=50&framing=huge", "framing")

    def test_framing_missing(self):
        self.check_invalid("?lens_mm=50", "framing")


if __name__ == "__main__":
    unittest.main()
