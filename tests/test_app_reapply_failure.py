import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class ReapplyFailureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def tearDown(self):
        self.fake.clear_failures()

    def test_reapply_failure_keeps_done_then_recovers(self):
        h, fake = self.harness, self.fake
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        sid = created["id"]
        record = h.wait_for_shot(sid, "done")
        self.assertEqual(len(record["versions"]), 1)

        fake.reset_cache()
        fake.fail("OpenOptics_DepthOfField", "Out of memory in Depth of Field")
        status, _ = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        self.assertEqual(status, 202)
        record = h.wait_until(sid, lambda r: r["status"] == "done" and r["reapply_error"] is not None,
                              what="done with reapply_error")
        self.assertEqual(record["status"], "done")
        self.assertIsNone(record["error"])
        self.assertEqual(record["reapply_error"]["code"], "job_failed")
        self.assertEqual(record["reapply_error"]["stage"], "optics")
        self.assertEqual(len(record["versions"]), 1)

        fake.clear_failures()
        fake.reset_cache()
        status, _ = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        self.assertEqual(status, 202)
        record = h.wait_until(sid, lambda r: r["status"] == "done" and r["reapply_error"] is None
                              and len(r["versions"]) == 2, what="second version")
        self.assertIsNone(record["error"])

    def test_first_optics_failure_then_reapply_recovers(self):
        h, fake = self.harness, self.fake
        fake.reset_cache()
        fake.fail("OpenOptics_DepthOfField")
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        sid = created["id"]
        record = h.wait_for_shot(sid, "failed")
        self.assertEqual(record["error"]["stage"], "optics")
        self.assertTrue(record["before_url"])

        fake.clear_failures()
        fake.reset_cache()
        status, _ = h.post(f"/api/shots/{sid}/reapply", {"aperture": 2.8})
        self.assertEqual(status, 202)
        record = h.wait_for_shot(sid, "done")
        self.assertEqual(len(record["versions"]), 1)
        self.assertIsNone(record["error"])
        self.assertIsNone(record["reapply_error"])

    def test_generation_failure_reapply_not_ready(self):
        h, fake = self.harness, self.fake
        fake.reset_cache()
        fake.fail("SamplerCustomAdvanced")
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        sid = created["id"]
        record = h.wait_for_shot(sid, "failed")
        self.assertEqual(record["error"]["stage"], "generate")
        status, body = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "not_ready")


if __name__ == "__main__":
    unittest.main()
