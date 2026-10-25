import asyncio
import threading
import unittest

from app.runner import ShotRunner


class CallDaemonTest(unittest.TestCase):
    def run_call(self, func, *args):
        runner = ShotRunner(None)
        return asyncio.run(runner._call(func, *args))

    def test_returns_value(self):
        self.assertEqual(self.run_call(lambda a, b: a + b, 2, 3), 5)

    def test_propagates_exception(self):
        def boom():
            raise ValueError("bad")

        with self.assertRaises(ValueError) as ctx:
            self.run_call(boom)
        self.assertEqual(str(ctx.exception), "bad")

    def test_thread_is_daemon(self):
        self.assertTrue(self.run_call(lambda: threading.current_thread().daemon))

    def test_cancel_does_not_wait_for_thread(self):
        release = threading.Event()

        async def main():
            runner = ShotRunner(None)
            task = asyncio.ensure_future(runner._call(release.wait, 10))
            await asyncio.sleep(0.05)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        try:
            asyncio.run(main())
        finally:
            release.set()


if __name__ == "__main__":
    unittest.main()
