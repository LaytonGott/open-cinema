import asyncio
import tempfile
import threading
import time
import unittest

from app.runner import ShotRunner
from app.store import ShotStore


class ShutdownTest(unittest.IsolatedAsyncioTestCase):
    async def test_stop_does_not_wait_for_blocked_sdk_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ShotRunner(ShotStore(tmp))
            entered = threading.Event()

            def blocked():
                entered.set()
                time.sleep(30)

            async def run_shot(shot_id):
                await runner._call(blocked)

            runner.run_shot = run_shot
            runner.start()
            runner.enqueue("s1")
            deadline = time.monotonic() + 5
            while not entered.is_set() and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            self.assertTrue(entered.is_set())
            started = time.monotonic()
            await runner.stop()
            self.assertLess(time.monotonic() - started, 2)


if __name__ == "__main__":
    unittest.main()
