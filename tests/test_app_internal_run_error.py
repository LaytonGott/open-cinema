import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from app import runner
from app.record import new_record
from app.store import ShotStore

PARAMS = {"description": "A woman walks.", "camera": "dolly-in", "lens_mm": 50,
          "aperture": 2.8, "framing": "full-body", "seed": 123}


async def wait_for(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting for condition")
        await asyncio.sleep(0.01)


class InternalRunErrorTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = ShotStore(Path(tmp.name))
        self.runner = runner.ShotRunner(self.store)
        self.runner.client = object()
        self.runner.start()
        self.addAsyncCleanup(self.runner.stop)

    async def test_internal_error_is_diagnosable(self):
        with mock.patch.object(runner.comfy, "submit_and_follow",
                               side_effect=RuntimeError("secret boom")):
            with self.assertLogs(runner.logger, level="ERROR") as logs:
                self.store.add(new_record("a", PARAMS))
                self.runner.enqueue("a")
                await wait_for(
                    lambda: self.store.get("a")["status"] in ("done", "failed"))
        record = self.store.get("a")
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["error"]["code"], "internal")
        self.assertIn("Check the console for details", record["error"]["message"])
        self.assertNotIn("secret boom", record["error"]["message"])
        output = "\n".join(logs.output)
        self.assertIn("Traceback", output)
        self.assertIn("secret boom", output)


if __name__ == "__main__":
    unittest.main()
