import asyncio
import tempfile
import unittest

from app.runner import ShotRunner
from app.store import ShotStore


def make_record(shot_id, status="queued"):
    return {"id": shot_id, "status": status, "progress": 0.0, "message": "",
            "stages": [{"id": "generate", "state": "pending"},
                       {"id": "optics", "state": "pending"}]}


class WorkerCancelTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_item_skipped_and_next_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            store.add(make_record("s1", "cancelled"))
            store.add(make_record("s2"))
            runner = ShotRunner(store)
            ran = []

            async def run_shot(shot_id):
                ran.append(shot_id)

            runner.run_shot = run_shot
            runner.start()
            try:
                runner.enqueue("s1")
                runner.items["s1"]["cancelled"] = True
                runner.enqueue("s2")
                await asyncio.wait_for(runner.queue.join(), 5)
                self.assertEqual(ran, ["s2"])
                self.assertEqual(runner.items, {})
            finally:
                await runner.stop()

    async def test_exception_after_cancel_finishes_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            store.add(make_record("s1", "generating"))
            store.add(make_record("s2"))
            runner = ShotRunner(store)
            ran = []

            async def run_shot(shot_id):
                if shot_id == "s1":
                    runner.cancel_requested = "s1"
                    raise RuntimeError("job cancelled")
                ran.append(shot_id)

            runner.run_shot = run_shot
            runner.start()
            try:
                runner.enqueue("s1")
                runner.enqueue("s2")
                await asyncio.wait_for(runner.queue.join(), 5)
                self.assertEqual(store.get("s1")["status"], "cancelled")
                self.assertEqual(ran, ["s2"])
                self.assertIsNone(runner.cancel_requested)
                self.assertIsNone(runner.current)
            finally:
                await runner.stop()


if __name__ == "__main__":
    unittest.main()
