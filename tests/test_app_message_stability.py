import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import progress
from app.record import new_record
from app.runner import ShotRunner
from app.store import ShotStore

PARAMS = {"description": "A woman walks.", "camera": "dolly-in", "lens_mm": 50,
          "aperture": 2.8, "framing": "full-body", "seed": 123}


class MessageForNodeTest(unittest.TestCase):
    def test_unknown_type_keeps_previous(self):
        self.assertEqual(
            progress.message_for_node(
                "generate", "NoSuchNode", previous="Decoding the video"),
            "Decoding the video")

    def test_waiting_with_unknown_type_gives_stage_default(self):
        self.assertEqual(progress.message_for_node(
            "generate", "NoSuchNode", previous="Waiting for ComfyUI"),
            "Generating video")
        self.assertEqual(progress.message_for_node(
            "optics", "NoSuchNode", previous="Waiting for ComfyUI"),
            "Estimating depth")


class RunnerMessageTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = ShotStore(tmp.name)
        self.runner = ShotRunner(self.store)
        self.record = new_record("a", PARAMS)
        self.store.add(self.record)

    async def test_unknown_node_leaves_message(self):
        self.runner.update(self.record, message="Decoding the video")
        self.runner.graph_types["a"] = {"1": "SamplerCustomAdvanced"}
        self.runner.apply_event(self.record, "generate", "progress", {
            "current_node": "99", "value": 0.5, "step": 1, "steps": 2,
            "nodes_total": 3})
        self.assertEqual(self.record["message"], "Decoding the video")

    async def test_message_not_waiting_once_running(self):
        self.record["message"] = "Waiting for ComfyUI"
        seen = []

        def fake_submit(client, graph, callback, on_job, guard):
            seen.append(self.record["message"])
            return object()

        with mock.patch("app.comfy.submit_and_follow", fake_submit), \
                mock.patch("app.comfy.download_output",
                           lambda *a: Path("before.mp4")):
            self.runner.client = object()
            await self.runner.run_generation(self.record)
        self.assertEqual(seen, ["Generating video"])
        self.assertNotEqual(self.record["message"], "Waiting for ComfyUI")


if __name__ == "__main__":
    unittest.main()
