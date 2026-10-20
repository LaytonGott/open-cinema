import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from app.record import public_record
from app.runner import ShotRunner
from app.store import ShotStore


class RecordingRunner(ShotRunner):
    def __init__(self, store):
        super().__init__(store)
        self.ran = []

    async def run_shot(self, shot_id):
        self.ran.append(shot_id)


class ShotRunnerTest(unittest.TestCase):
    def test_runs_in_order(self):
        async def main():
            runner = RecordingRunner(None)
            runner.start()
            for shot_id in ("a", "b", "c"):
                runner.enqueue(shot_id)
            deadline = time.monotonic() + 5
            while len(runner.ran) < 3 and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            await runner.stop()
            return runner.ran

        self.assertEqual(asyncio.run(main()), ["a", "b", "c"])

    def test_update_applies_and_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({"id": "s1", "message": ""})
            runner = ShotRunner(store)
            runner.update(record, message="x")
            self.assertEqual(record["message"], "x")
            self.assertGreaterEqual(record["elapsed_s"], 0)
            self.assertIn("_started", record)
            other = ShotStore(tmp)
            other.load_all()
            self.assertEqual(other.get("s1")["message"], "x")
            self.assertEqual(other.get("s1")["elapsed_s"], record["elapsed_s"])
            public = public_record(record)
            self.assertNotIn("_started", public)
            self.assertEqual(public["message"], "x")

    def test_apply_event_progress_never_falls(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({"id": "s1", "progress": 0.0, "message": "", "stages": [
                {"id": "generate", "progress": 0.0},
                {"id": "optics", "progress": 0.0}]})
            runner = ShotRunner(store)

            def event(value, step=None, steps=None):
                return {"current_node": "KSampler", "value": value,
                        "step": step, "steps": steps}

            runner.apply_event(record, "generate", "status", "queued")
            self.assertEqual(record["progress"], 0.0)
            seen = []
            for value, step in ((0.25, 2), (0.5, 4), (0.2, 1), (1.0, 8)):
                runner.apply_event(record, "generate", "progress", event(value, step, 8))
                seen.append(record["progress"])
                if value == 0.2:
                    self.assertEqual(record["message"], "Generating video: step 1 of 8")
            self.assertEqual(seen, sorted(seen))
            self.assertAlmostEqual(seen[0], 0.2125, places=6)
            self.assertAlmostEqual(seen[2], 0.425, places=6)
            self.assertAlmostEqual(seen[3], 0.85, places=6)
            self.assertEqual(record["stages"][0]["progress"], 1.0)
            runner.apply_event(record, "optics", "progress", {
                "current_node": "DA3Node", "value": 0.5, "step": None, "steps": None})
            self.assertAlmostEqual(record["progress"], 0.925, places=6)
            self.assertEqual(record["message"], "Estimating depth")

    def test_thread_callback_schedules_on_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({"id": "s1", "progress": 0.0, "stages": []})
            runner = ShotRunner(store)

            async def main():
                loop = asyncio.get_running_loop()
                callback = runner.thread_callback(loop, record, "generate")
                await loop.run_in_executor(None, callback, "progress", {
                    "current_node": None, "value": 1.0, "step": None, "steps": None})
                await asyncio.sleep(0.05)

            asyncio.run(main())
            self.assertAlmostEqual(record["progress"], 0.85, places=6)
            self.assertEqual(record["message"], "Generating video")

    def test_run_generation_downloads_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({
                "id": "s1", "status": "queued", "progress": 0.0, "message": "",
                "params": {"seed": 7}, "derived": {"prompt": "a cat"},
                "stages": [{"id": "generate", "state": "pending", "progress": 0.0}]})
            runner = ShotRunner(store)
            runner.client = object()
            seen = {}

            def fake_submit(client, graph, on_event, on_job=None):
                seen["graph"] = graph
                return "job"

            def fake_download(job, node_id, dest_dir, stem):
                path = Path(dest_dir) / (stem + ".webm")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
                return path

            with mock.patch("app.comfy.submit_and_follow", fake_submit), \
                    mock.patch("app.comfy.download_output", fake_download):
                asyncio.run(runner.run_generation(record))
            self.assertEqual(record["before_url"], "/media/s1/before.webm")
            self.assertEqual(record["stages"][0]["state"], "done")
            self.assertAlmostEqual(record["progress"], 0.85, places=6)
            self.assertIn("opencinema/s1/before", json.dumps(seen["graph"]))

    def test_prepare_optics_uploads_and_builds_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            record = store.add({
                "id": "s1", "before_url": "/media/s1/before.mp4",
                "params": {"lens_mm": 50}, "derived": {"subject_distance_m": 3.0}})
            shot_dir = Path(store.shot_dir("s1"))
            shot_dir.mkdir(parents=True, exist_ok=True)
            (shot_dir / "before.mp4").write_bytes(b"x")
            runner = ShotRunner(store)
            uploaded = []

            def fake_upload(client, path):
                uploaded.append(Path(path))
                return "uploaded.mp4"

            with mock.patch("app.comfy.make_client", lambda: "client"), \
                    mock.patch("app.comfy.upload_video", fake_upload):
                client, graph = runner.prepare_optics(record, 2.8, 1)
            self.assertEqual(client, "client")
            self.assertEqual(uploaded, [shot_dir / "before.mp4"])
            self.assertEqual(graph["1"]["inputs"]["file"], "uploaded.mp4")
            text = json.dumps(graph)
            self.assertIn("2.8", text)
            self.assertIn("opencinema/s1/after_1", text)

    def test_run_shot_runs_generation_then_optics(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            store.add({
                "id": "s1", "status": "queued", "progress": 0.0, "message": "",
                "params": {"seed": 7, "lens_mm": 50, "aperture": 2.8},
                "derived": {"prompt": "a cat", "subject_distance_m": 3.0},
                "stages": [{"id": "generate", "state": "pending", "progress": 0.0},
                           {"id": "optics", "state": "pending", "progress": 0.0}]})
            runner = ShotRunner(store)

            def fake_download(job, node_id, dest_dir, stem):
                path = Path(dest_dir) / (stem + ".mp4")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
                return path

            with mock.patch("app.comfy.make_client", lambda: "client"), \
                    mock.patch("app.comfy.upload_video", lambda c, p: "up.mp4"), \
                    mock.patch("app.comfy.submit_and_follow",
                               lambda client, graph, on_event, on_job=None: "job"), \
                    mock.patch("app.comfy.download_output", fake_download):
                asyncio.run(runner.run_shot("s1"))
            record = store.get("s1")
            self.assertEqual(len(record["versions"]), 1)
            version = record["versions"][0]
            self.assertEqual(version["n"], 1)
            self.assertEqual(version["aperture"], 2.8)
            self.assertEqual(version["url"], "/media/s1/after_1.mp4")
            self.assertTrue(version["created_at"].endswith("Z"))
            self.assertEqual(record["current_version"], 1)
            self.assertEqual(record["status"], "done")
            self.assertEqual(record["progress"], 1.0)
            self.assertEqual(record["message"], "Done")

    def test_internal_error_marks_failed_and_continues(self):
        class FailingFirst(RecordingRunner):
            async def run_shot(self, shot_id):
                if not self.ran:
                    self.ran.append(shot_id)
                    raise RuntimeError("boom")
                await super().run_shot(shot_id)

        with tempfile.TemporaryDirectory() as tmp:
            store = ShotStore(tmp)
            store.add({"id": "s1", "status": "running"})
            store.add({"id": "s2", "status": "running"})

            async def main():
                runner = FailingFirst(store)
                runner.start()
                runner.enqueue("s1")
                runner.enqueue("s2")
                deadline = time.monotonic() + 5
                while len(runner.ran) < 2 and time.monotonic() < deadline:
                    await asyncio.sleep(0.01)
                await runner.queue.join()
                await runner.stop()
                return runner.ran

            with self.assertLogs("app.runner", level="ERROR"):
                ran = asyncio.run(main())
            self.assertEqual(ran, ["s1", "s2"])
            error = store.get("s1")["error"]
            self.assertEqual(store.get("s1")["status"], "failed")
            self.assertEqual(error["code"], "internal")
            self.assertEqual(
                error["message"],
                "Something went wrong inside Open Cinema. "
                "Check the console for details.")
            self.assertEqual(error["stage"], "generate")
            self.assertNotIn("Traceback", str(error))
            self.assertNotIn("boom", str(error))


if __name__ == "__main__":
    unittest.main()
