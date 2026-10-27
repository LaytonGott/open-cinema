import json
import tempfile
import unittest
from pathlib import Path

from app.store import SAMPLES_DIR, SAMPLES_MARKER, ShotStore, seed_samples


class SeedSamplesTest(unittest.TestCase):
    def test_bundled_sample_is_a_finished_shot_with_its_videos(self):
        record = json.loads((SAMPLES_DIR / "sample-red-coat" / "shot.json").read_text(encoding="utf-8"))
        self.assertEqual(record["id"], "sample-red-coat")
        self.assertEqual(record["status"], "done")
        self.assertGreaterEqual(len(record["versions"]), 3)
        self.assertTrue((SAMPLES_DIR / "sample-red-coat" / "before.mp4").is_file())
        for version in record["versions"]:
            self.assertTrue(version["url"].startswith("/media/sample-red-coat/"))
            self.assertTrue((SAMPLES_DIR / "sample-red-coat" / version["url"].rsplit("/", 1)[1]).is_file())
        current = [v for v in record["versions"] if v["n"] == record["current_version"]]
        self.assertEqual(current[0]["aperture"], 1.4)

    def test_new_data_dir_gets_the_samples_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(seed_samples(tmp), ["sample-red-coat"])
            store = ShotStore(tmp)
            store.load_all()
            self.assertEqual([r["id"] for r in store.list()], ["sample-red-coat"])
            store.remove("sample-red-coat")
            self.assertEqual(seed_samples(tmp), [])
            self.assertTrue((Path(tmp) / SAMPLES_MARKER).is_file())
            again = ShotStore(tmp)
            again.load_all()
            self.assertEqual(again.list(), [])

    def test_existing_shot_folder_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "shots" / "sample-red-coat"
            target.mkdir(parents=True)
            (target / "shot.json").write_text("{}", encoding="utf-8")
            self.assertEqual(seed_samples(tmp), [])
            self.assertEqual((target / "shot.json").read_text(encoding="utf-8"), "{}")

    def test_missing_samples_folder_does_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(seed_samples(tmp, Path(tmp) / "nope"), [])
            self.assertFalse((Path(tmp) / SAMPLES_MARKER).exists())


if __name__ == "__main__":
    unittest.main()
