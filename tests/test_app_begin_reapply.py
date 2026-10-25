import tempfile
import unittest

from app.record import public_record
from app.runner import ShotRunner
from app.store import ShotStore


class BeginReapplyTest(unittest.TestCase):
    def test_begin_reapply_sets_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({
                "id": "s1", "status": "done", "progress": 1.0, "message": "Done",
                "error": "old error",
                "versions": [{"n": 1, "aperture": 2.8, "url": "u"}],
                "current_version": 1,
                "stages": [{"id": "generate", "state": "done", "progress": 1.0},
                           {"id": "optics", "state": "done", "progress": 1.0}]})
            runner = ShotRunner(store)
            runner.begin_reapply(record, 4.0)
            other = ShotStore(tmp)
            other.load_all()
            saved = other.get("s1")
            self.assertEqual(saved["status"], "optics")
            self.assertEqual(saved["progress"], 0.0)
            self.assertEqual(saved["message"], "Waiting for ComfyUI")
            self.assertTrue(saved["_reapply"])
            self.assertEqual(saved["stages"][0]["state"], "done")
            self.assertEqual(saved["stages"][1]["state"], "active")
            self.assertEqual(saved["stages"][1]["progress"], 0.0)
            self.assertIsNone(saved["error"])
            self.assertEqual(saved["_reapply_aperture"], 4.0)
            public = public_record(record)
            self.assertFalse([k for k in public if k.startswith("_")])
            self.assertNotIn("reapply_aperture", public)


if __name__ == "__main__":
    unittest.main()
