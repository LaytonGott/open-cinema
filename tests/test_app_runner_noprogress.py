import tempfile
import unittest

from app.record import new_record
from app.runner import ShotRunner
from app.store import ShotStore

PARAMS = {"description": "A woman walks.", "camera": "dolly-in", "lens_mm": 50,
          "aperture": 2.8, "framing": "full-body", "seed": 123}


class NoProgressEventsTest(unittest.TestCase):
    def make(self, tmp):
        store = ShotStore(tmp)
        record = store.add(new_record("abc", PARAMS))
        return ShotRunner(store), record

    def test_status_only_events_leave_progress_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            for stage in ("generate", "optics"):
                for text in ("queued", "running", "success"):
                    runner.apply_event(record, stage, "status", text)
                    self.assertEqual(record["progress"], 0.0)
                    self.assertEqual(record["message"], "Waiting for ComfyUI")
                    self.assertIsInstance(record["elapsed_s"], (int, float))

    def test_lower_progress_event_does_not_lower_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            high = {"current_node": "x", "value": 0.8, "step": 8, "steps": 10}
            low = dict(high, value=0.2, step=2)
            runner.apply_event(record, "generate", "progress", high)
            before = record["progress"]
            runner.apply_event(record, "generate", "progress", low)
            self.assertAlmostEqual(record["progress"], before, places=6)
            self.assertAlmostEqual(record["stages"][0]["progress"], 0.8, places=6)
            runner.apply_event(record, "generate", "status", "running")
            self.assertAlmostEqual(record["progress"], before, places=6)
            self.assertIsInstance(record["elapsed_s"], (int, float))


if __name__ == "__main__":
    unittest.main()
