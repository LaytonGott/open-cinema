import tempfile
import unittest

from app.record import new_record
from app.runner import ShotRunner
from app.store import ShotStore

PARAMS = {"description": "A woman walks.", "camera": "dolly-in", "lens_mm": 50,
          "aperture": 2.8, "framing": "full-body", "seed": 123}


class RunnerWatchTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = ShotStore(tmp.name)
        self.runner = ShotRunner(self.store)
        self.record = new_record("a", PARAMS)
        self.store.add(self.record)
        self.other = new_record("b", PARAMS)
        self.store.add(self.other)

    async def test_set_after_update(self):
        event = self.runner.watch("a")
        self.assertFalse(event.is_set())
        self.runner.update(self.record, progress=0.5)
        self.assertTrue(event.is_set())

    async def test_not_set_after_unwatch(self):
        event = self.runner.watch("a")
        self.runner.unwatch("a", event)
        self.runner.update(self.record, progress=0.5)
        self.assertFalse(event.is_set())

    async def test_other_shot_does_not_set(self):
        event = self.runner.watch("a")
        self.runner.update(self.other, progress=0.5)
        self.assertFalse(event.is_set())


if __name__ == "__main__":
    unittest.main()
