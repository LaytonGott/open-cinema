import unittest

import httpx
from comfy_sdk.exceptions import ComfyError

from app.errors import ComfyUnreachable
from app.outage import OutageGuard, is_transient


class FakeTime:
    def __init__(self):
        self.now = 0.0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def comfy_error(status):
    exc = ComfyError("boom")
    exc.http_status = status
    return exc


def failing(exc, times, result="ok"):
    """Return a function that raises `exc` `times` times, then returns `result`."""
    state = {"n": 0}

    def func():
        state["n"] += 1
        if state["n"] <= times:
            raise exc
        return result

    return func


class OutageGuardTest(unittest.TestCase):
    def setUp(self):
        self.time = FakeTime()
        self.guard = OutageGuard(
            window=25.0, pause=1.5, clock=self.time.clock, sleep=self.time.sleep
        )

    def test_is_transient(self):
        self.assertTrue(is_transient(httpx.ConnectError("x")))
        self.assertTrue(is_transient(ConnectionError()))
        self.assertTrue(is_transient(TimeoutError()))
        self.assertFalse(is_transient(LookupError()))
        self.assertFalse(is_transient(ValueError()))

    def test_comfy_error_status(self):
        for status in (502, 503, 504):
            self.assertTrue(is_transient(comfy_error(status)))
        self.assertFalse(is_transient(comfy_error(404)))
        self.assertFalse(is_transient(ComfyError("no status")))

    def test_retry_then_success(self):
        self.assertEqual(self.guard.call(failing(ConnectionError(), 2)), "ok")
        self.assertAlmostEqual(self.time.now, 3.0, places=6)

    def test_success_resets_streak(self):
        self.guard.call(failing(ConnectionError(), 10))
        self.time.now += 100
        # A fresh streak starts now; 10 failures (15 s) stay under the 25 s window.
        self.assertEqual(self.guard.call(failing(ConnectionError(), 10)), "ok")

    def test_continuous_failures_raise_unreachable(self):
        with self.assertRaises(ComfyUnreachable) as ctx:
            self.guard.call(failing(httpx.ConnectError("down"), 10**6))
        self.assertIsInstance(ctx.exception.__cause__, httpx.ConnectError)
        self.assertAlmostEqual(self.time.now, 25.5, delta=1.5)

    def test_non_transient_propagates_at_once(self):
        with self.assertRaises(LookupError):
            self.guard.call(failing(LookupError("x"), 1))
        self.assertEqual(self.time.now, 0.0)

    def test_404_propagates_503_retries(self):
        self.assertEqual(self.guard.call(failing(comfy_error(503), 1)), "ok")
        with self.assertRaises(ComfyError):
            self.guard.call(failing(comfy_error(404), 1))


if __name__ == "__main__":
    unittest.main()
