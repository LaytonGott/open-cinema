import tempfile
import unittest

from app import progress
from app.runner import ShotRunner
from app.store import ShotStore


def make_record(store, **extra):
    record = {"id": "s1", "status": "optics", "progress": 0.0, "message": "",
              "stages": [{"id": "generate", "state": "done", "progress": 1.0},
                         {"id": "optics", "state": "active", "progress": 0.0}]}
    record.update(extra)
    return store.add(record)


DATA = {"current_node": "1", "value": 0.5, "step": 1, "steps": 2}


class ReapplyProgressTest(unittest.TestCase):
    def test_reapply_progress_is_stage_fraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = make_record(store, _reapply=True)
            ShotRunner(store).apply_event(record, "optics", "progress", DATA)
            self.assertAlmostEqual(record["progress"], 0.5, places=6)

    def test_first_run_progress_uses_optics_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = make_record(store)
            ShotRunner(store).apply_event(record, "optics", "progress", DATA)
            self.assertAlmostEqual(
                record["progress"], progress.optics_progress(0.5), places=6)


class BeginReapplyClearsErrorTest(unittest.TestCase):
    def test_begin_reapply_clears_error_and_waits(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = make_record(store, status="failed", error="boom",
                                 message="boom")
            ShotRunner(store).begin_reapply(record, 4.0)
            self.assertIsNone(record["error"])
            self.assertEqual(record["message"], "Waiting for ComfyUI")


if __name__ == "__main__":
    unittest.main()
