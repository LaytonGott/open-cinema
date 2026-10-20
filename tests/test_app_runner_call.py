import threading
import unittest
from unittest import mock

from app import errors, runner


def make_runner():
    r = runner.ShotRunner(store=None, comfyui_url="http://comfy.invalid")
    r.watch_interval = 0.01
    return r


class CallTest(unittest.IsolatedAsyncioTestCase):
    async def test_result_returned(self):
        async def check(url):
            return {"reachable": True}

        with mock.patch.object(runner.comfy_health, "check_health", check):
            self.assertEqual(await make_runner()._call(lambda a, b: a + b, 1, 2), 3)

    async def test_no_url_just_awaits(self):
        r = runner.ShotRunner(store=None)
        self.assertEqual(await r._call(lambda: "ok"), "ok")

    async def test_unreachable_after_three_failures(self):
        release = threading.Event()
        count = 0

        async def check(url):
            nonlocal count
            count += 1
            return {"reachable": False}

        with mock.patch.object(runner.comfy_health, "check_health", check):
            try:
                with self.assertRaises(errors.ComfyUnreachable):
                    await make_runner()._call(release.wait)
            finally:
                release.set()
        self.assertEqual(count, 3)

    async def test_success_resets_counter(self):
        release = threading.Event()
        results = [False, False, True, False, False, True]

        async def check(url):
            if not results:
                release.set()
                return {"reachable": True}
            return {"reachable": results.pop(0)}

        with mock.patch.object(runner.comfy_health, "check_health", check):
            self.assertTrue(await make_runner()._call(release.wait, 5))
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
