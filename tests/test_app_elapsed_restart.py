import tempfile
import unittest

from app.store import ShotStore


class ElapsedRestartTests(unittest.TestCase):
    def test_run_clock_not_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({"id": "s1", "status": "optics", "_started": 123.4, "elapsed_s": 5.5})
            text = (store.shot_dir("s1") / "shot.json").read_text(encoding="utf-8")
            self.assertNotIn("_started", text)
            self.assertIn("_started", record)
            self.assertEqual(record["elapsed_s"], 5.5)

            again = ShotStore(tmp)
            again.load_all()
            again.recover_interrupted()
            loaded = again.get("s1")
            self.assertNotIn("_started", loaded)
            self.assertEqual(loaded["elapsed_s"], 0.0)
            self.assertEqual(loaded["status"], "failed")

    def test_finished_shot_keeps_elapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            store.add({"id": "s2", "status": "done", "elapsed_s": 7.2})
            again = ShotStore(tmp)
            again.load_all()
            self.assertEqual(again.get("s2")["elapsed_s"], 7.2)


if __name__ == "__main__":
    unittest.main()
