import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class TestRejectedGeneration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_unet_name_not_offered(self):
        h = self.harness
        fake = self.fake
        fake.reset_cache()
        required = fake.object_info["UnetLoaderGGUF"]["input"]["required"]
        orig = required["unet_name"]
        required["unet_name"] = [["only-another-model.gguf"]]
        try:
            status, created = h.post("/api/shots", {**SHOT, "seed": 401})
            self.assertEqual(status, 201)
            h.wait_for_shot(created["id"], "failed")
            code, record = h.get(f"/api/shots/{created['id']}")
        finally:
            required["unet_name"] = orig
        self.assertEqual(record["error"]["code"], "comfy_rejected")
        self.assertEqual(record["error"]["stage"], "generate")
        self.assertIn("unet_name", record["error"]["message"])


class TestRejectedOptics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_quality_not_offered(self):
        h = self.harness
        fake = self.fake
        fake.reset_cache()
        required = fake.object_info["OpenOptics_DepthOfField"]["input"]["required"]
        orig = required["quality"]
        required["quality"] = [["draft"]]
        try:
            status, created = h.post("/api/shots", {**SHOT, "seed": 402})
            self.assertEqual(status, 201)
            h.wait_for_shot(created["id"], "failed")
            code, record = h.get(f"/api/shots/{created['id']}")
        finally:
            required["quality"] = orig
        self.assertEqual(record["error"]["code"], "comfy_rejected")
        self.assertEqual(record["error"]["stage"], "optics")
        self.assertTrue(record.get("before_url"))
        self.assertIn("quality", record["error"]["message"])


if __name__ == "__main__":
    unittest.main()
