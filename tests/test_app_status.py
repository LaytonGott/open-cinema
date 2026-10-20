import time
import unittest

from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy

ORDER = ["queued", "generating", "optics", "done"]
EARLY = ("Generating video", "Waiting for ComfyUI")
LATE = ("Estimating depth", "Applying depth of field")


class StatusTest(unittest.TestCase):
    def test_status_stages_messages_and_elapsed(self):
        fake = FakeComfy()
        try:
            fake.start()
            with AppHarness(fake=fake) as harness:
                code, body = harness.post("/api/shots", SHOT)
                self.assertEqual(code, 201)
                shot_id = body["id"]
                samples = []

                def collect(record):
                    samples.append(record)
                    return record["status"] in ("done", "failed", "cancelled")

                final = harness.wait_until(shot_id, collect, timeout=90, what="shot done")
                self.assertEqual(final["status"], "done")

                statuses = [s["status"] for s in samples]
                indexes = [ORDER.index(s) for s in statuses]
                self.assertEqual(indexes, sorted(indexes), statuses)

                progress = [s["progress"] for s in samples]
                self.assertEqual(progress, sorted(progress), progress)
                self.assertEqual(progress[-1], 1)

                for s in samples:
                    stages = {e["id"]: e["state"] for e in s["stages"]}
                    if stages["generate"] != "done":
                        self.assertNotEqual(stages["optics"], "active", s)

                messages = []
                for s in samples:
                    if not messages or messages[-1] != s["message"]:
                        messages.append(s["message"])
                self.assertGreaterEqual(len(set(messages)), 2, messages)
                self.assertEqual(messages[-1], "Done")
                early = [i for i, m in enumerate(messages) if m.startswith(EARLY)]
                late = [i for i, m in enumerate(messages) if m.startswith(LATE)]
                self.assertTrue(early, messages)
                if late:
                    self.assertLess(early[0], late[0], messages)

                first = harness.get(f"/api/shots/{shot_id}")[1]["elapsed_s"]
                self.assertGreater(first, 0)
                deadline = time.time() + 0.3
                while time.time() < deadline:
                    time.sleep(0.05)
                second = harness.get(f"/api/shots/{shot_id}")[1]["elapsed_s"]
                self.assertEqual(first, second)
        finally:
            fake.release()
            fake.stop()


if __name__ == "__main__":
    unittest.main()
