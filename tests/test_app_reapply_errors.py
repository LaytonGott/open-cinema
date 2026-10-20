import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class ReapplyErrorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def _done_shot(self):
        h = self.harness
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        try:
            h.wait_for_shot(created["id"], "done")
        except AssertionError as e:
            raise AssertionError(f"{e}\n{h.log()}") from None
        return created["id"]

    def test_reapply_unknown_id_404(self):
        status, body = self.harness.post("/api/shots/nope/reapply", {"aperture": 8})
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

    def test_reapply_bad_aperture_400(self):
        sid = self._done_shot()
        status, body = self.harness.post(f"/api/shots/{sid}/reapply", {"aperture": 3})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_shot")

    def test_reapply_not_ready_409(self):
        h, fake = self.harness, self.fake
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        try:
            status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
            self.assertEqual(status, 201)
            sid = created["id"]
            h.wait_until(sid, lambda r: r["status"] == "generating", what="generating")
            status, body = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
            self.assertEqual(status, 409)
            self.assertEqual(body["error"]["code"], "not_ready")
        finally:
            fake.release()
        h.wait_for_shot(sid, "done")

    def test_reapply_busy_409(self):
        h, fake = self.harness, self.fake
        sid = self._done_shot()
        fake.hold_at("OpenOptics_DepthOfField")
        try:
            status, body = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
            self.assertEqual(status, 202)
            self.assertEqual(body["status"], "optics")
            status, body = h.post(f"/api/shots/{sid}/reapply", {"aperture": 5.6})
            self.assertEqual(status, 409)
            self.assertEqual(body["error"]["code"], "busy")
        finally:
            fake.release()
        h.wait_for_shot(sid, "done")


if __name__ == "__main__":
    unittest.main()
