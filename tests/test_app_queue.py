import time
import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy

BUSY = ("generating", "optics")


class QueueTest(unittest.TestCase):
    def test_three_shots_run_in_order(self):
        fake = FakeComfy()
        try:
            fake.start()
            fake.hold_at("SamplerCustomAdvanced")
            with AppHarness(fake=fake) as harness:
                ids = []
                for seed in (1, 2, 3):
                    status, body = harness.post("/api/shots", dict(SHOT, seed=seed))
                    self.assertEqual(status, 201)
                    ids.append(body["id"])
                self.assertEqual(len(set(ids)), 3)

                harness.wait_until(ids[0], lambda r: r["status"] == "generating", what="shot 1 generating")
                for shot_id in ids[1:]:
                    record = harness.wait_until(shot_id, lambda r: r["status"] == "queued", what="queued shot")
                    self.assertIn("Waiting for ComfyUI", record["message"])
                _, first = harness.get(f"/api/shots/{ids[0]}")
                self.assertEqual(first["status"], "generating")

                fake.release()
                first_seen = {ids[0]: 0}
                done = set()
                deadline = time.time() + 120
                while len(done) < 3 and time.time() < deadline:
                    code, listing = harness.get("/api/shots")
                    self.assertEqual(code, 200)
                    statuses = {r["id"]: r["status"] for r in listing["shots"] if r["id"] in ids}
                    for shot_id, status in statuses.items():
                        if status == "generating":
                            first_seen.setdefault(shot_id, len(first_seen))
                        if status in ("done", "failed", "cancelled"):
                            done.add(shot_id)
                    busy = [s for s in statuses.values() if s in BUSY]
                    self.assertLessEqual(len(busy), 1, f"more than one shot busy: {statuses}")
                    time.sleep(0.05)
                self.assertEqual(len(done), 3, "not all shots finished")
                for shot_id in ids:
                    self.assertEqual(harness.wait_for_shot(shot_id)["status"], "done")
                self.assertEqual(sorted(first_seen, key=first_seen.get), [i for i in ids if i in first_seen])
        finally:
            fake.release()
            fake.stop()


if __name__ == "__main__":
    unittest.main()
