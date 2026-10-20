import asyncio
import tempfile
import time
import unittest

from app.record import public_record
from app.runner import ShotRunner
from app.store import ShotStore


class RecordingRunner(ShotRunner):
    def __init__(self, store):
        super().__init__(store)
        self.ran = []

    async def run_shot(self, shot_id):
        self.ran.append(shot_id)


class ShotRunnerTest(unittest.TestCase):
    def test_runs_in_order(self):
        async def main():
            runner = RecordingRunner(None)
            runner.start()
            for shot_id in ("a", "b", "c"):
                runner.enqueue(shot_id)
            deadline = time.monotonic() + 5
            while len(runner.ran) < 3 and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            await runner.stop()
            return runner.ran

        self.assertEqual(asyncio.run(main()), ["a", "b", "c"])

    def test_update_applies_and_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({"id": "s1", "message": ""})
            runner = ShotRunner(store)
            runner.update(record, message="x")
            self.assertEqual(record["message"], "x")
            self.assertGreaterEqual(record["elapsed_s"], 0)
            self.assertIn("_started", record)
            other = ShotStore(tmp)
            other.load_all()
            self.assertEqual(other.get("s1")["message"], "x")
            self.assertEqual(other.get("s1")["elapsed_s"], record["elapsed_s"])
            public = public_record(record)
            self.assertNotIn("_started", public)
            self.assertEqual(public["message"], "x")

    def test_internal_error_marks_failed_and_continues(self):
        class FailingFirst(RecordingRunner):
            async def run_shot(self, shot_id):
                if not self.ran:
                    self.ran.append(shot_id)
                    raise RuntimeError("boom")
                await super().run_shot(shot_id)

        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            store.add({"id": "s1", "status": "running"})
            store.add({"id": "s2", "status": "running"})

            async def main():
                runner = FailingFirst(store)
                runner.start()
                runner.enqueue("s1")
                runner.enqueue("s2")
                deadline = time.monotonic() + 5
                while len(runner.ran) < 2 and time.monotonic() < deadline:
                    await asyncio.sleep(0.01)
                await runner.queue.join()
                await runner.stop()
                return runner.ran

            with self.assertLogs("app.runner", level="ERROR"):
                ran = asyncio.run(main())
            self.assertEqual(ran, ["s1", "s2"])
            error = store.get("s1")["error"]
            self.assertEqual(store.get("s1")["status"], "failed")
            self.assertEqual(error["code"], "internal")
            self.assertEqual(
                error["message"],
                "Something went wrong inside Open Cinema. "
                "Check the console for details.")
            self.assertEqual(error["stage"], "generate")
            self.assertNotIn("Traceback", str(error))
            self.assertNotIn("boom", str(error))


if __name__ == "__main__":
    unittest.main()
