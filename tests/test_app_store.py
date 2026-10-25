import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.store import ShotStore, new_shot_id

ROOT = Path(__file__).resolve().parent.parent


class ShotIdTests(unittest.TestCase):
    def test_id_format(self):
        self.assertRegex(new_shot_id(), r"^\d{8}-\d{6}-[0-9a-f]{4}$")

    def test_ids_unique(self):
        existing = set()
        for _ in range(200):
            existing.add(new_shot_id(existing))
        self.assertEqual(len(existing), 200)


class ShotStoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def test_same_second_order_and_reload(self):
        store = ShotStore(self.dir)
        ids = ["20250101-000000-ffff", "20250101-000000-0000", "20250101-000000-8888"]
        for shot_id in ids:
            store.add({"id": shot_id})
        self.assertEqual([r["id"] for r in store.list()], ids)
        fresh = ShotStore(self.dir)
        fresh.load_all()
        self.assertEqual([r["id"] for r in fresh.list()], ids)
        for shot_id in ids:
            self.assertEqual(fresh.get(shot_id), store.get(shot_id))

    def test_corrupt_shot_json_skipped_with_warning(self):
        store = ShotStore(self.dir)
        store.add({"id": "20250101-000000-aaaa"})
        store.add({"id": "20250101-000001-bbbb"})
        bad = store.shot_dir("20250101-000002-cccc")
        bad.mkdir(parents=True)
        (bad / "shot.json").write_text("{not json", encoding="utf-8")
        fresh = ShotStore(self.dir)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            fresh.load_all()
        self.assertEqual([r["id"] for r in fresh.list()], ["20250101-000000-aaaa", "20250101-000001-bbbb"])
        self.assertIn("warning", err.getvalue())
        self.assertIn("20250101-000002-cccc", err.getvalue())

    def test_remove_deletes_folder(self):
        store = ShotStore(self.dir)
        store.add({"id": "20250101-000000-aaaa"})
        folder = store.shot_dir("20250101-000000-aaaa")
        self.assertTrue(folder.is_dir())
        store.remove("20250101-000000-aaaa")
        self.assertFalse(folder.exists())
        self.assertIsNone(store.get("20250101-000000-aaaa"))


class ShotStoreLockedDeleteTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.shot_id = "20250101-000000-aaaa"
        self.store = ShotStore(self.dir)
        self.store.add({"id": self.shot_id})
        self.folder = self.store.shot_dir(self.shot_id)
        (self.folder / "before.mp4").write_bytes(b"video")

    def test_locked_file_and_folder_leave_no_half_shot(self):
        with mock.patch("app.store.shutil.rmtree"), mock.patch("app.store.os.rename", side_effect=PermissionError):
            self.store.remove(self.shot_id)
        self.assertIsNone(self.store.get(self.shot_id))
        self.assertNotIn(self.shot_id, [r["id"] for r in self.store.list()])
        fresh = ShotStore(self.dir)
        fresh.load_all()
        self.assertEqual(fresh.list(), [])

    def test_locked_file_original_folder_is_gone(self):
        with mock.patch("app.store.shutil.rmtree"):
            self.store.remove(self.shot_id)
        self.assertFalse(self.folder.exists())


class GitignoreTests(unittest.TestCase):
    def test_app_data_ignored(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("app/data/", [line.strip() for line in lines])


if __name__ == "__main__":
    unittest.main()
