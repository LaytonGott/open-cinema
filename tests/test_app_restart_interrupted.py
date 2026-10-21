import time
import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


class RestartInterruptedTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeComfy()
        self.harness = AppHarness(fake=self.fake).start()
        self.addCleanup(self.fake.close)
        self.addCleanup(self.harness.stop)

    def _create(self, seed):
        status, created = self.harness.post("/api/shots", {**SHOT, "seed": seed})
        self.assertEqual(status, 201)
        return created["id"]

    def test_hard_kill_during_generation(self):
        h, fake = self.harness, self.fake
        first = self._create(1)
        first_done = h.wait_for_shot(first, "done")
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        try:
            second = self._create(2)
            h.wait_until(second, lambda r: r["status"] == "generating", what="second generating")
            order_before = [s["id"] for s in h.get("/api/shots")[1]["shots"]]
            h.stop_app()  # the process is killed, not asked to shut down
            h.start_app()
        finally:
            fake.release()

        record = h.wait_for_shot(second, "failed")
        self.assertEqual(record["error"]["code"], "interrupted")
        self.assertEqual(record["error"]["stage"], "generate")

        _, again = h.get(f"/api/shots/{first}")
        self.assertEqual(again["status"], "done")
        self.assertEqual(again, first_done)
        self.assertEqual([s["id"] for s in h.get("/api/shots")[1]["shots"]], order_before)

        prompts = len(fake.prompts)
        deadline = time.time() + 1.0
        while time.time() < deadline:
            _, now = h.get(f"/api/shots/{second}")
            self.assertEqual(now, record)
            self.assertEqual(len(fake.prompts), prompts)
            time.sleep(0.1)

        third = self._create(3)
        h.wait_for_shot(third, "done")


if __name__ == "__main__":
    unittest.main()
