import tempfile
import unittest

from app.record import new_record
from app.runner import ShotRunner
from app.store import ShotStore

PARAMS = {"description": "A woman walks.", "camera": "dolly-in", "lens_mm": 50,
          "aperture": 2.8, "framing": "full-body", "seed": 123}


class ProgressFramesTest(unittest.TestCase):
    def make(self, tmp):
        store = ShotStore(tmp)
        record = store.add(new_record("abc", PARAMS))
        return ShotRunner(store), record

    def test_step_frame_keeps_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            frame = {"current_node": "x", "value": 1.0, "step": 4, "steps": 4,
                     "nodes_total": 0, "nodes_done": 0}
            runner.apply_event(record, "generate", "progress", frame)
            self.assertEqual(record["progress"], 0.0)
            self.assertEqual(record["stages"][0]["progress"], 0.0)

    def test_overall_frame_sets_fraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            frame = {"current_node": "x", "value": 0.5, "step": 0, "steps": 0,
                     "nodes_total": 10, "nodes_done": 5}
            runner.apply_event(record, "generate", "progress", frame)
            self.assertAlmostEqual(record["stages"][0]["progress"], 0.5, places=6)
            self.assertGreater(record["progress"], 0.0)

    def test_progress_never_decreases(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            high = {"current_node": "x", "value": 0.5, "step": 0, "steps": 0,
                    "nodes_total": 10, "nodes_done": 5}
            runner.apply_event(record, "generate", "progress", high)
            before = record["progress"]
            runner.apply_event(record, "generate", "progress",
                               dict(high, value=0.2, nodes_done=2))
            self.assertAlmostEqual(record["progress"], before, places=6)
            self.assertAlmostEqual(record["stages"][0]["progress"], 0.5, places=6)


if __name__ == "__main__":
    unittest.main()
