"""Ride out short ComfyUI outages: retry transient failures, give up after a window.

All durations are in seconds.
"""

import time

import httpx
from comfy_sdk.exceptions import ComfyError

from app.errors import ComfyUnreachable

TRANSIENT_STATUSES = (502, 503, 504)


def _status(exc):
    """Return the HTTP status code (int) carried by `exc`, or None."""
    for name in ("http_status", "status_code"):
        value = getattr(exc, name, None)
        if isinstance(value, int):
            return value
    value = getattr(getattr(exc, "response", None), "status_code", None)
    return value if isinstance(value, int) else None


def is_transient(exc):
    """Return True if `exc` is a failure worth retrying, else False.

    Transient: `httpx.TransportError`, `ConnectionError`, `TimeoutError`, and a
    `ComfyError` or `httpx.HTTPStatusError` whose HTTP status is 502, 503 or 504.
    """
    if isinstance(exc, (httpx.TransportError, ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, (ComfyError, httpx.HTTPStatusError)):
        return _status(exc) in TRANSIENT_STATUSES
    return False


class OutageGuard:
    """Retry transient failures until they last `window` seconds, then give up.

    `pause` is the sleep in seconds between retries; `clock` returns seconds
    (monotonic) and `sleep` takes seconds. `stop` is an optional
    `threading.Event`: once it is set (the app is shutting down) a failure is
    re-raised at once and the pause between retries ends early, so a retrying
    worker thread never holds the process up.
    """

    def __init__(self, window=25.0, pause=1.5, clock=time.monotonic, sleep=None, stop=None):
        self.window = window
        self.pause = pause
        self.clock = clock
        self.stop = stop
        self.sleep = sleep or (stop.wait if stop is not None else time.sleep)
        self._first = None

    def ok(self):
        """Record a success: the failure streak ends. Returns None."""
        self._first = None

    def failed(self, exc):
        """Handle one failure `exc` of the current streak. Returns None.

        Re-raises `exc` at once when it is not transient. Raises
        `ComfyUnreachable` (chained from `exc`) once the streak has lasted
        `window` seconds; otherwise sleeps `pause` seconds and returns.
        """
        if not is_transient(exc) or (self.stop is not None and self.stop.is_set()):
            raise exc
        now = self.clock()
        if self._first is None:
            self._first = now
        if now - self._first >= self.window:
            raise ComfyUnreachable(str(exc)) from exc
        self.sleep(self.pause)

    def call(self, func, *args):
        """Return `func(*args)`, retrying while it fails transiently."""
        while True:
            try:
                result = func(*args)
            except Exception as exc:
                self.failed(exc)
            else:
                self.ok()
                return result
