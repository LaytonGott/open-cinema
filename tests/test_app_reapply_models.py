import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy

MODEL = "depth_anything_3_mono_large.safetensors"


class ReapplyModelsMissingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_reapply_refused_when_model_file_missing(self):
        h, fake = self.harness, self.fake
        h.reset()
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        sid = created["id"]
        h.wait_for_shot(sid, "done")
        required = fake.object_info["LoadDA3Model"]["input"]["required"]
        orig = required["model_name"]
        required["model_name"] = [["only-another-model.safetensors"]]
        try:
            _, before = h.get(f"/api/shots/{sid}")
            status, body = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
            _, after = h.get(f"/api/shots/{sid}")
        finally:
            required["model_name"] = orig
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "comfy_models_missing")
        self.assertIn(f"model_name '{MODEL}' (LoadDA3Model)", body["error"]["message"])
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
