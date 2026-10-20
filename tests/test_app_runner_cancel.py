import tempfile
import unittest

from app.runner import ShotRunner
from app.store import ShotStore


class FakeJob:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class RunnerCancelTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_queued_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            store.add({"id": "s1", "status": "queued", "progress": 0.0, "message": ""})
            runner = ShotRunner(store)
            runner.start()
            try:
                runner.items["s1"] = {"shot_id": "s1", "aperture": None,
                                      "cancelled": False, "started": False}
                result = await runner.cancel("s1")
                self.assertEqual(result["id"], "s1")
                self.assertTrue(runner.items["s1"]["cancelled"])
                self.assertEqual(store.get("s1")["status"], "cancelled")
            finally:
                await runner.stop()

    async def test_cancel_running_calls_job_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            store.add({"id": "s1", "status": "generating", "progress": 0.2, "message": ""})
            runner = ShotRunner(store)
            job = FakeJob()
            runner.current = {"shot_id": "s1", "job": job}
            runner.items["s1"] = {"shot_id": "s1", "aperture": None,
                                  "cancelled": False, "started": True}
            result = await runner.cancel("s1")
            self.assertEqual(result["id"], "s1")
            self.assertTrue(job.cancelled)
            self.assertEqual(runner.cancel_requested, "s1")

    async def test_cancel_not_running_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            store.add({"id": "s1", "status": "done", "progress": 1.0, "message": "Done"})
            runner = ShotRunner(store)
            self.assertIsNone(await runner.cancel("s1"))
            self.assertIsNone(await runner.cancel("nope"))


if __name__ == "__main__":
    unittest.main()
