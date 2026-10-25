import datetime
import tempfile
import unittest

from app.store import ShotStore


class CreatedAtTest(unittest.TestCase):
    def test_created_at_is_utc_with_z(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = ShotStore(tmp).add({"id": "shot-1"})
        created = record["created_at"]
        self.assertRegex(created, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        parsed = datetime.datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        self.assertAlmostEqual(parsed.timestamp(), now.timestamp(), delta=5)


if __name__ == "__main__":
    unittest.main()
