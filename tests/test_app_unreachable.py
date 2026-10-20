import time
import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class UnreachableTest(unittest.TestCase):
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

    def test_comfy_stops_mid_run_and_recovers(self):
        h, fake = self.harness, self.fake
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        stopped = False
        try:
            a = self._create(301)
            b = self._create(302)
            h.wait_until(a, lambda r: r["status"] == "generating", what="A generating")
            time.sleep(0.5)
            fake.release()
            fake.stop()
            stopped = True
            t0 = time.time()
            record = h.wait_for_shot(a, "failed", timeout=30)
            elapsed = time.time() - t0
            error = record.get("error") or {}
            self.assertEqual(error.get("code"), "comfy_unreachable", error)
            self.assertEqual(error.get("stage"), "generate")
            self.assertTrue(error.get("message"))
            self.assertNotIn("Traceback", error["message"])
            self.assertLess(elapsed, 30)
        finally:
            fake.release()
            if stopped:
                fake.start()
        # the queue moved on: B reaches a terminal state, then a new shot completes
        h.wait_until(b, lambda r: r["status"] in ("done", "failed", "cancelled"), timeout=60, what="B finished")
        c = self._create(303)
        h.wait_for_shot(c, "done")


if __name__ == "__main__":
    unittest.main()
