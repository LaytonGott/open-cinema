import time
import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class CancelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def _create(self, seed):
        status, created = self.harness.post("/api/shots", {**SHOT, "seed": seed})
        self.assertEqual(status, 201)
        return created["id"]

    def test_cancel_generating_shot(self):
        h, fake = self.harness, self.fake
        fake.reset_cache()
        errors_before = sum(1 for e in fake.history.values() if e["status"]["status_str"] == "error")
        fake.hold_at("SamplerCustomAdvanced")
        try:
            a = self._create(101)
            b = self._create(102)
            h.wait_until(a, lambda r: r["status"] == "generating", what="A generating")
            status, body = h.post(f"/api/shots/{a}/cancel")
            self.assertEqual(status, 200)
            self.assertEqual(body["status"], "cancelled")
        finally:
            fake.release()
        h.wait_until(b, lambda r: r["status"] in ("generating", "done"), what="B generating")
        h.wait_for_shot(b, "done")
        code, record = h.get(f"/api/shots/{a}")
        self.assertEqual(record["status"], "cancelled")
        # the fake saw the cancel: it interrupted A's prompt, which it records in history as an error
        interrupted = [e for e in fake.history.values() if e["status"]["status_str"] == "error"]
        self.assertEqual(len(interrupted) - errors_before, 1)

    def test_cancel_queued_shot(self):
        h, fake = self.harness, self.fake
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        try:
            a = self._create(201)
            h.wait_until(a, lambda r: r["status"] == "generating", what="A generating")
            c = self._create(202)
            status, body = h.post(f"/api/shots/{c}/cancel")
            self.assertEqual(status, 200)
            self.assertEqual(body["status"], "cancelled")
        finally:
            fake.release()
        h.wait_for_shot(a, "done")
        time.sleep(0.5)
        code, record = h.get(f"/api/shots/{c}")
        self.assertEqual(record["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
