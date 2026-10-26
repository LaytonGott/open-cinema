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
            status, body = h.post("/api/shots", {**SHOT, "seed": 401})
        finally:
            required["unet_name"] = orig
        # the missing model is reported when the shot is created, before anything is generated
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "comfy_models_missing")
        self.assertIn("unet_name", body["error"]["message"])
        self.assertEqual(h.get("/api/shots")[1]["shots"], [])


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
        try:
            status, created = h.post("/api/shots", {**SHOT, "seed": 402})
            self.assertEqual(status, 201)
            # ComfyUI stops offering the value after the shot was accepted (the check before a shot cannot see that)
            required["quality"] = [["draft"]]
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
