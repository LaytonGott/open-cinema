import asyncio
import tempfile
import unittest
from unittest import mock

from app import errors
from app.record import new_record
from app.runner import ShotRunner
from app.store import ShotStore

PARAMS = {"description": "A woman walks.", "camera": "dolly-in", "lens_mm": 50,
          "aperture": 2.8, "framing": "full-body", "seed": 123}


class UnreachableTest(unittest.IsolatedAsyncioTestCase):
    async def test_comfy_unreachable_fails_the_shot_and_the_queue_moves_on(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = ShotStore(tmp.name)
        for shot_id in ("a", "b"):
            store.add(new_record(shot_id, PARAMS))
        runner = ShotRunner(store)
        runner.client = object()
        runner.start()
        self.addAsyncCleanup(runner.stop)

        def outage(*args):
            raise errors.ComfyUnreachable("ComfyUI stopped answering")

        with mock.patch("app.runner.comfy.submit_and_follow", outage):
            runner.enqueue("a")
            runner.enqueue("b")
            await asyncio.wait_for(runner.queue.join(), 30)
        for shot_id in ("a", "b"):
            record = store.get(shot_id)
            self.assertEqual(record["status"], "failed")
            self.assertEqual(record["error"]["code"], "comfy_unreachable")
            self.assertEqual(record["error"]["stage"], "generate")
            self.assertNotIn("Traceback", record["error"]["message"])


if __name__ == "__main__":
    unittest.main()
