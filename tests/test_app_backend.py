import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy

RECORD_KEYS = {
    "id", "created_at", "params", "derived", "status", "progress", "message", "stages",
    "elapsed_s", "error", "reapply_error", "before_url", "versions", "current_version",
}


class BackendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = AppHarness(fake=FakeComfy()).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()

    def test_create_shot(self):
        status, record = self.harness.post("/api/shots", SHOT)
        self.assertEqual(status, 201)
        self.assertRegex(record["id"], r"^\d{8}-\d{6}-[0-9a-f]{4}$")
        self.assertEqual(record["status"], "queued")
        self.assertEqual(set(record), RECORD_KEYS)
        self.assertEqual(record["params"]["seed"], 7)

    def test_invalid_shot(self):
        status, body = self.harness.post("/api/shots", {"description": "x"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_shot")
        status, body = self.harness.post("/api/shots", [1])
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_shot")


if __name__ == "__main__":
    unittest.main()
