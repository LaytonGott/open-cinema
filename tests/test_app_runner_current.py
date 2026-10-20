import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.runner import ShotRunner
from app.store import ShotStore


class FakeJob:
    def __init__(self):
        self.cancelled = 0

    def cancel(self):
        self.cancelled += 1


def fake_download(job, node_id, dest_dir, stem):
    path = Path(dest_dir) / (stem + ".mp4")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


def make(tmp):
    store = ShotStore(tmp)
    record = store.add({
        "id": "s1", "status": "queued", "progress": 0.0, "message": "",
        "params": {"seed": 7}, "derived": {"prompt": "a cat"},
        "stages": [{"id": "generate", "state": "pending", "progress": 0.0}]})
    runner = ShotRunner(store)
    runner.client = object()
    return runner, record


class RunnerCurrentTest(unittest.TestCase):
    def run_stage(self, runner, record, stub):
        with mock.patch("app.comfy.submit_and_follow", stub), \
                mock.patch("app.comfy.download_output", fake_download):
            asyncio.run(runner.run_generation(record))

    def test_current_set_during_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = make(tmp)
            job = FakeJob()
            seen = []

            def stub(client, graph, on_event, on_job=None):
                on_job(job)
                seen.append(runner.current)
                return "job"

            self.run_stage(runner, record, stub)
            self.assertIs(seen[0]["job"], job)
            self.assertEqual(seen[0]["shot_id"], "s1")

    def test_current_cleared_after_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = make(tmp)

            def ok(client, graph, on_event, on_job=None):
                on_job(FakeJob())
                return "job"

            self.run_stage(runner, record, ok)
            self.assertIsNone(runner.current)

            def boom(client, graph, on_event, on_job=None):
                on_job(FakeJob())
                raise RuntimeError("boom")

            with self.assertRaises(RuntimeError):
                self.run_stage(runner, record, boom)
            self.assertIsNone(runner.current)

    def test_cancel_requested_cancels_job_on_arrival(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = make(tmp)
            runner.cancel_requested = "s1"
            job = FakeJob()

            def stub(client, graph, on_event, on_job=None):
                on_job(job)
                return "job"

            self.run_stage(runner, record, stub)
            self.assertEqual(job.cancelled, 1)


if __name__ == "__main__":
    unittest.main()
