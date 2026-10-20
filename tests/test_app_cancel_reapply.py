import json
import time
import unittest
import urllib.request

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class CancelReapplyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def _create_done(self, seed):
        status, created = self.harness.post("/api/shots", {**SHOT, "seed": seed})
        self.assertEqual(status, 201)
        self.harness.wait_for_shot(created["id"], "done")
        return created["id"]

    def _wait_fake_running(self, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with urllib.request.urlopen(self.fake.url + "/queue", timeout=5) as r:
                if json.load(r)["queue_running"]:
                    return
            time.sleep(0.02)
        self.fail("the fake never started the re-apply prompt")

    def test_cancel_reapply_keeps_version(self):
        h, fake = self.harness, self.fake
        sid = self._create_done(301)
        fake.hold_at("OpenOptics_DepthOfField")
        try:
            status, body = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
            self.assertEqual(status, 202)
            self._wait_fake_running()
            status, body = h.post(f"/api/shots/{sid}/cancel")
            self.assertEqual(status, 200)
            self.assertEqual(body["status"], "done")
            self.assertEqual(len(body["versions"]), 1)
            self.assertEqual(body["current_version"], 1)
        finally:
            fake.release()

    def test_cancel_not_running(self):
        h = self.harness
        sid = self._create_done(302)
        status, body = h.post(f"/api/shots/{sid}/cancel")
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "not_running")
        status, body = h.post("/api/shots/doesnotexist/cancel")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
