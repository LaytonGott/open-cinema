import json
import tempfile
import unittest
from pathlib import Path

from app.runner import ShotRunner
from app.store import ShotStore


def stages():
    return [{"id": "generate", "state": "done", "progress": 1.0},
            {"id": "optics", "state": "active", "progress": 0.4}]


class FinishCancelTest(unittest.TestCase):
    def test_finish_cancel_without_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({"id": "s1", "status": "optics", "progress": 0.3,
                                "message": "Working", "stages": stages()})
            ShotRunner(store)._finish_cancel(record)
            other = ShotStore(tmp)
            other.load_all()
            saved = other.get("s1")
            self.assertEqual(saved["status"], "cancelled")
            self.assertEqual(saved["message"], "Cancelled.")
            self.assertIsNone(saved["error"])
            self.assertNotIn("active", [s["state"] for s in saved["stages"]])
            self.assertEqual(saved["stages"][1]["state"], "pending")

    def test_finish_cancel_with_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({
                "id": "s1", "status": "optics", "progress": 0.3,
                "message": "Working", "_reapply": True,
                "versions": [{"n": 1, "aperture": 2.8, "url": "u"}],
                "stages": stages()})
            ShotRunner(store)._finish_cancel(record)
            other = ShotStore(tmp)
            other.load_all()
            saved = other.get("s1")
            self.assertEqual(saved["status"], "done")
            self.assertEqual(saved["progress"], 1.0)
            self.assertEqual(saved["message"], "Done")
            self.assertNotIn("_reapply", saved)
            for path in Path(tmp).rglob("shot.json"):
                self.assertNotIn("_reapply", json.loads(path.read_text()))
            self.assertEqual(saved["stages"][1]["state"], "done")
            self.assertIsNone(saved["error"])
            self.assertNotIn("active", [s["state"] for s in saved["stages"]])
            self.assertEqual(len(saved["versions"]), 1)


if __name__ == "__main__":
    unittest.main()
