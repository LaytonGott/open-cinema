import asyncio
import json
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


class RunnerFailuresTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.store = ShotStore(self.tmp)
        self.runner = runner.ShotRunner(self.store)
        self.runner.client = object()
        self.runner.start()
        self.addAsyncCleanup(self.runner.stop)

    def add_shot(self, shot_id):
        self.store.add(new_record(shot_id, PARAMS))
        self.runner.enqueue(shot_id)

    def finished(self, shot_id):
        return lambda: self.store.get(shot_id)["status"] in ("done", "failed")

    async def test_download_failure(self):
        with mock.patch.object(runner.comfy, "submit_and_follow", return_value=object()), \
                mock.patch.object(runner.comfy, "download_output",
                                  side_effect=OSError("disk gone")):
            self.add_shot("a")
            await wait_for(self.finished("a"))
        record = self.store.get("a")
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["error"]["code"], "download_failed")
        self.assertTrue(record["error"]["message"])

    async def test_internal_error_is_hidden(self):
        with mock.patch.object(runner.comfy, "submit_and_follow",
                               side_effect=RuntimeError("boom secret")):
            with self.assertLogs(runner.logger, level="ERROR") as logs:
                self.add_shot("a")
                await wait_for(self.finished("a"))
        record = self.store.get("a")
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["error"]["code"], "internal")
        self.assertNotIn("Traceback", record["message"])
        self.assertNotIn("boom secret", record["message"])
        saved = (self.store.shot_dir("a") / "shot.json").read_text(encoding="utf-8")
        json.loads(saved)
        self.assertNotIn("Traceback", saved)
        self.assertNotIn("boom secret", saved)
        self.assertIn("Traceback", "\n".join(logs.output))
        self.assertIn("boom secret", "\n".join(logs.output))

    async def test_worker_survives_failure(self):
        results = [RuntimeError("boom secret"), object(), object()]
        with mock.patch.object(runner.comfy, "submit_and_follow", side_effect=results), \
                mock.patch.object(runner.comfy, "download_output",
                                  return_value=Path("out.mp4")), \
                mock.patch.object(runner.ShotRunner, "prepare_optics",
                                  return_value=(object(), {})):
            with self.assertLogs(runner.logger, level="ERROR"):
                self.add_shot("a")
                await wait_for(self.finished("a"))
            self.assertEqual(self.store.get("a")["status"], "failed")
            self.add_shot("b")
            await wait_for(self.finished("b"))
        self.assertEqual(self.store.get("b")["status"], "done")


if __name__ == "__main__":
    unittest.main()
