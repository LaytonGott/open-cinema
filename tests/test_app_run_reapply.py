import asyncio
import unittest

from app.runner import ShotRunner


class StoreStub:
    def __init__(self, record):
        self.record = record

    def get(self, shot_id):
        return self.record


def reapply(record, aperture):
    runner = ShotRunner(StoreStub(record))
    calls = []

    async def fake_optics(rec, ap, n):
        calls.append((rec["id"], ap, n))

    runner.run_optics = fake_optics
    asyncio.run(runner.run_reapply(record["id"], aperture))
    return calls


class RunReapplyTests(unittest.TestCase):
    def test_reapply_uses_max_version_plus_one(self):
        record = {"id": "s1", "versions": [{"n": 1}, {"n": 2}]}
        self.assertEqual(reapply(record, 2.8), [("s1", 2.8, 3)])

    def test_reapply_without_versions_uses_n_1(self):
        self.assertEqual(reapply({"id": "s2"}, 4.0), [("s2", 4.0, 1)])


if __name__ == "__main__":
    unittest.main()
