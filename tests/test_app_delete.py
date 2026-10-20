import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class DeleteShotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def _shot_ids(self):
        status, body = self.harness.get("/api/shots")
        self.assertEqual(status, 200)
        shots = body["shots"] if isinstance(body, dict) else body
        return [s["id"] for s in shots]

    def test_delete_done_shot_then_restart(self):
        h = self.harness
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        sid = created["id"]
        try:
            h.wait_for_shot(sid, "done")
        except AssertionError as e:
            raise AssertionError(f"{e}\n{h.log()}") from None
        folder = h.data_dir / "shots" / sid
        self.assertTrue(folder.exists())

        status, _ = h.request("DELETE", f"/api/shots/{sid}")
        self.assertEqual(status, 204)
        status, body = h.get(f"/api/shots/{sid}")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertNotIn(sid, self._shot_ids())
        self.assertFalse(folder.exists())

        h.restart_app()
        self.assertNotIn(sid, self._shot_ids())
        status, body = h.get(f"/api/shots/{sid}")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

    def test_delete_unknown_id_404(self):
        status, body = self.harness.request("DELETE", "/api/shots/nope")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

    def test_delete_generating_busy_409(self):
        h, fake = self.harness, self.fake
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        try:
            status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
            self.assertEqual(status, 201)
            sid = created["id"]
            h.wait_until(sid, lambda r: r["status"] == "generating", what="generating")
            status, body = h.request("DELETE", f"/api/shots/{sid}")
            self.assertEqual(status, 409)
            self.assertEqual(body["error"]["code"], "busy")
        finally:
            fake.release()
        h.wait_for_shot(sid, "done")


if __name__ == "__main__":
    unittest.main()
