import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class SubmitDownTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()
        cls.fake.stop()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_submit_refused_when_comfy_down(self):
        status, before = self.harness.get("/api/shots")
        self.assertEqual(status, 200)
        status, body = self.harness.post("/api/shots", SHOT)
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "comfy_unreachable")
        self.assertTrue(body["error"]["message"])
        self.assertNotIn("Traceback", body["error"]["message"])
        status, after = self.harness.get("/api/shots")
        self.assertEqual(status, 200)
        self.assertEqual(len(after["shots"]), len(before["shots"]))

    def test_invalid_body_still_400_when_comfy_down(self):
        status, body = self.harness.post("/api/shots", {"description": "x"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_shot")


if __name__ == "__main__":
    unittest.main()
