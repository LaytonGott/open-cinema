import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class DerivedTest(unittest.TestCase):
    def test_derived_prompt_and_distance(self):
        fake = FakeComfy()
        try:
            fake.start()
            with AppHarness(fake=fake) as harness:
                shot = dict(
                    SHOT,
                    description="A tired detective lights a cigarette",
                    camera="dolly-in",
                    lens_mm=50,
                    framing="full-body",
                )
                status, body = harness.post("/api/shots", shot)
                self.assertEqual(status, 201)
                derived = body["derived"]
                self.assertAlmostEqual(derived["subject_distance_m"], 5.1005, places=4)
                self.assertTrue(derived["prompt"].startswith(
                    "Full-body shot, the whole figure visible head to toe. "
                    "A tired detective lights a cigarette."))
                self.assertIn("Slow dolly-in toward the subject", derived["prompt"])
                self.assertIn("50 mm lens look", derived["prompt"])

                record = harness.wait_for_shot(body["id"])
                self.assertEqual(record["derived"], derived)
        finally:
            fake.close()


if __name__ == "__main__":
    unittest.main()
