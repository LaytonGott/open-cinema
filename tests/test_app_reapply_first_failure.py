import json
import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class ReapplyFirstFailureTest(unittest.TestCase):
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

    def test_failed_reapply_with_no_versions_clears_marker(self):
        h, fake = self.harness, self.fake
        h.reset()
        fake.fail("OpenOptics_DepthOfField")
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        sid = created["id"]
        h.wait_for_shot(sid, "failed")

        fake.reset_cache()
        status, _ = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        self.assertEqual(status, 202)
        record = h.wait_until(
            sid, lambda r: r["status"] == "failed" and r["error"] is not None
            and r["error"]["stage"] == "optics" and r["message"] == r["error"]["message"],
            what="failed re-apply")
        self.assertEqual(record["error"]["stage"], "optics")
        self.assertEqual(record["versions"], [])

        paths = [p for p in h.data_dir.rglob("shot.json") if p.parent.name == sid]
        self.assertEqual(len(paths), 1)
        saved = json.loads(paths[0].read_text(encoding="utf-8"))
        self.assertNotIn("_reapply", saved)
        self.assertNotIn("_reapply_aperture", saved)


if __name__ == "__main__":
    unittest.main()
