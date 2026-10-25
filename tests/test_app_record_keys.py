import unittest

from tests.app_harness import SHOT, AppHarness

RECORD_KEYS = {
    "id", "created_at", "params", "derived", "status", "progress", "message", "stages",
    "elapsed_s", "error", "reapply_error", "before_url", "versions", "current_version",
}


class RecordKeysTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = AppHarness().start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()

    def test_record_keys_match_spec(self):
        h = self.harness
        h.reset()
        status, shot = h.post("/api/shots", SHOT)
        self.assertIn(status, (200, 201, 202), shot)
        sid = shot["id"]
        record = h.wait_for_shot(sid, "done")
        self.assertEqual(set(record), RECORD_KEYS)

        status, body = h.post(f"/api/shots/{sid}/reapply", {"aperture": 5.6})
        self.assertIn(status, (200, 201, 202), body)
        status, record = h.get(f"/api/shots/{sid}")
        self.assertEqual(status, 200)
        self.assertEqual(set(record), RECORD_KEYS)

        record = h.wait_for_shot(sid, "done")
        self.assertEqual(set(record), RECORD_KEYS)


if __name__ == "__main__":
    unittest.main()
