import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.store import ShotStore, replace_with_retry

REAL_REPLACE = os.replace


class ReplaceRetryTests(unittest.TestCase):
    def test_succeeds_after_two_failures(self):
        with mock.patch("app.store.os.replace", side_effect=[PermissionError(), PermissionError(), None]) as rep, \
                mock.patch("app.store.time.sleep"):
            replace_with_retry("a", "b")
        self.assertEqual(rep.call_count, 3)

    def test_raises_oserror_after_three_failures(self):
        with mock.patch("app.store.os.replace", side_effect=PermissionError()) as rep, \
                mock.patch("app.store.time.sleep"):
            with self.assertRaises(OSError) as ctx:
                replace_with_retry("a", "b")
        self.assertEqual(rep.call_count, 3)
        self.assertIn("locked", str(ctx.exception))

    def test_save_writes_shot_json_after_one_failure(self):
        calls = []

        def flaky(src, dst):
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError()
            REAL_REPLACE(src, dst)

        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            with mock.patch("app.store.os.replace", side_effect=flaky), mock.patch("app.store.time.sleep"):
                store.save({"id": "s1", "status": "done"})
            data = json.loads((Path(tmp) / "shots" / "s1" / "shot.json").read_text(encoding="utf-8"))
        self.assertEqual(data["id"], "s1")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
