import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class JobFailedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def _failed_record(self, seed):
        h = self.harness
        status, created = h.post("/api/shots", {**SHOT, "seed": seed})
        self.assertEqual(status, 201)
        h.wait_for_shot(created["id"], "failed")
        code, record = h.get(f"/api/shots/{created['id']}")
        return record

    def test_generate_stage_failure(self):
        fake = self.fake
        fake.reset_cache()
        fake.fail("SamplerCustomAdvanced", "The sampler exploded")
        try:
            record = self._failed_record(301)
        finally:
            fake.clear_failures()
        self.assertEqual(record["error"]["code"], "job_failed")
        self.assertEqual(record["error"]["stage"], "generate")
        self.assertIn("The sampler exploded", record["error"]["message"])
        self.assertIn("SamplerCustomAdvanced", record["error"]["message"])
        self.assertIsNone(record["before_url"])
        self.assertEqual(record["stages"][0]["state"], "failed")

    def test_optics_stage_failure(self):
        fake = self.fake
        fake.reset_cache()
        fake.fail("DA3Inference", "Depth model crashed")
        try:
            record = self._failed_record(302)
        finally:
            fake.clear_failures()
        self.assertEqual(record["error"]["code"], "job_failed")
        self.assertEqual(record["error"]["stage"], "optics")
        self.assertIn("DA3Inference", record["error"]["message"])
        self.assertTrue(record["before_url"])
        self.assertEqual(record["versions"], [])
        self.assertEqual([s["state"] for s in record["stages"]], ["done", "failed"])


if __name__ == "__main__":
    unittest.main()
