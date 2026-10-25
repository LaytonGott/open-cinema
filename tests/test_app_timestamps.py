import datetime
import tempfile
import time
import unittest

from app.store import ShotStore
from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy

STAMP = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"


def utc_seconds(stamp):
    parsed = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    return parsed.timestamp()


class CreatedAtTest(unittest.TestCase):
    def test_created_at_is_utc_with_z(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = ShotStore(tmp).add({"id": "shot-1"})
        created = record["created_at"]
        self.assertRegex(created, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        parsed = datetime.datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        self.assertAlmostEqual(parsed.timestamp(), now.timestamp(), delta=5)


class VersionCreatedAtTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_versions_created_at_is_utc_with_z_after_reapply(self):
        h = self.harness
        h.reset()
        status, created = h.post("/api/shots", SHOT)
        self.assertEqual(status, 201)
        sid = created["id"]
        h.wait_for_shot(sid, "done")
        status, _ = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        self.assertEqual(status, 202)
        deadline = time.time() + 60
        while time.time() < deadline:
            code, record = h.get(f"/api/shots/{sid}")
            self.assertEqual(code, 200)
            if record["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.02)
        self.assertEqual(record["status"], "done", h.log())
        self.assertEqual([v["n"] for v in record["versions"]], [1, 2])
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        for stamp in [record["created_at"]] + [v["created_at"] for v in record["versions"]]:
            self.assertRegex(stamp, STAMP)
            self.assertAlmostEqual(utc_seconds(stamp), now, delta=120)


if __name__ == "__main__":
    unittest.main()
