import threading
import unittest
from unittest import mock

from app import errors, runner


def make_runner():
    return runner.ShotRunner(store=None, comfyui_url="http://comfy.invalid")


class CallTest(unittest.IsolatedAsyncioTestCase):
    async def test_result_returned(self):
        self.assertEqual(await make_runner()._call(lambda a, b: a + b, 1, 2), 3)

    async def test_no_url_just_awaits(self):
        r = runner.ShotRunner(store=None)
        self.assertEqual(await r._call(lambda: "ok"), "ok")

    async def test_slow_thread_with_unreachable_health_still_returns(self):
        done = threading.Event()
        timer = threading.Timer(0.2, done.set)

        async def check(url):
            return {"reachable": False}

        with mock.patch("app.comfy_health.check_health", check):
            timer.start()
            self.addCleanup(timer.cancel)
            self.assertTrue(await make_runner()._call(done.wait, 5))

    async def test_unreachable_from_thread_propagates(self):
        def func():
            raise errors.ComfyUnreachable("gone")

        with self.assertRaises(errors.ComfyUnreachable):
            await make_runner()._call(func)

    async def test_other_exception_propagates_unchanged(self):
        def func():
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            await make_runner()._call(func)


if __name__ == "__main__":
    unittest.main()
