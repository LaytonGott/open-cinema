import asyncio
import time
import unittest

from app.runner import ShotRunner


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


if __name__ == "__main__":
    unittest.main()
