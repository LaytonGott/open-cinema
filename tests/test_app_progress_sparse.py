import tempfile
import unittest

from app.record import new_record
from app.runner import ShotRunner
from app.store import ShotStore

PARAMS = {"description": "A woman walks.", "camera": "dolly-in", "lens_mm": 50,
          "aperture": 2.8, "framing": "full-body", "seed": 123}


def frame(value, nodes_total=1):
    return {"current_node": "x", "value": value, "step": 1, "steps": 10,
            "nodes_total": nodes_total}


class SparseProgressTest(unittest.TestCase):
    def make(self, tmp):
        store = ShotStore(tmp)
        record = store.add(new_record("abc", PARAMS))
        return ShotRunner(store), record

    def test_lower_second_frame_keeps_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            runner.apply_event(record, "generate", "progress", frame(0.2))
            after_first = record["progress"]
            runner.apply_event(record, "generate", "progress", frame(0.1))
            self.assertAlmostEqual(record["progress"], after_first, places=6)
            self.assertLess(record["progress"], 1)
            self.assertAlmostEqual(record["stages"][0]["progress"], 0.2, places=6)

    def test_out_of_order_frames_never_lower_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            overall = 0.0
            stage = 0.0
            for value in (0.5, 0.3, 0.6, 0.4):
                runner.apply_event(record, "generate", "progress", frame(value))
                self.assertGreaterEqual(record["progress"], overall)
                self.assertGreaterEqual(record["stages"][0]["progress"], stage)
                overall = record["progress"]
                stage = record["stages"][0]["progress"]

    def test_step_frame_leaves_progress_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            runner.apply_event(record, "generate", "progress", frame(0.3))
            overall = record["progress"]
            stage = record["stages"][0]["progress"]
            runner.apply_event(record, "generate", "progress", frame(0.9, 0))
            self.assertEqual(record["progress"], overall)
            self.assertEqual(record["stages"][0]["progress"], stage)


if __name__ == "__main__":
    unittest.main()
