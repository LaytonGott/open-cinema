import tempfile
import time
import unittest

from app.record import public_record
from app.runner import ShotRunner
from app.store import ShotStore


class ElapsedRunTest(unittest.TestCase):
    def test_begin_reapply_starts_new_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({
                "id": "s1", "status": "done", "progress": 1.0, "message": "Done",
                "_started": time.monotonic() - 100, "elapsed_s": 100.0,
                "stages": [{"id": "generate", "state": "done", "progress": 1.0},
                           {"id": "optics", "state": "done", "progress": 1.0}]})
            runner = ShotRunner(store)
            runner.begin_reapply(record, 2.8)
            self.assertEqual(record["status"], "optics")
            self.assertLess(public_record(record)["elapsed_s"], 2)


if __name__ == "__main__":
    unittest.main()
