import tempfile
import unittest

from app.record import new_record
from app.runner import ShotRunner
from app.store import ShotStore

PARAMS = {"description": "A woman walks.", "camera": "dolly-in", "lens_mm": 50,
          "aperture": 2.8, "framing": "full-body", "seed": 123}


class ProgressFramesTest(unittest.TestCase):
    def make(self, tmp):
        store = ShotStore(tmp)
        record = store.add(new_record("abc", PARAMS))
        return ShotRunner(store), record

    def test_step_frame_keeps_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            frame = {"current_node": "x", "value": 1.0, "step": 4, "steps": 4,
                     "nodes_total": 0, "nodes_done": 0}
            runner.apply_event(record, "generate", "progress", frame)
            self.assertEqual(record["progress"], 0.0)
            self.assertEqual(record["stages"][0]["progress"], 0.0)

    def test_overall_frame_sets_fraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            frame = {"current_node": "x", "value": 0.5, "step": 0, "steps": 0,
                     "nodes_total": 10, "nodes_done": 5}
            runner.apply_event(record, "generate", "progress", frame)
            self.assertAlmostEqual(record["stages"][0]["progress"], 0.5, places=6)
            self.assertGreater(record["progress"], 0.0)

    def test_progress_never_decreases(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            high = {"current_node": "x", "value": 0.5, "step": 0, "steps": 0,
                    "nodes_total": 10, "nodes_done": 5}
            runner.apply_event(record, "generate", "progress", high)
            before = record["progress"]
            runner.apply_event(record, "generate", "progress",
                               dict(high, value=0.2, nodes_done=2))
            self.assertAlmostEqual(record["progress"], before, places=6)
            self.assertAlmostEqual(record["stages"][0]["progress"], 0.5, places=6)

    def test_generate_stage_stays_below_one_after_both_samplers(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp)
            # the graph in the order its nodes run: two samplers (24 each), the decode (12) and the save (2)
            runner.graph_types[record["id"]] = {
                "15": "SamplerCustomAdvanced", "24": "SamplerCustomAdvanced", "26": "VAEDecodeTiled", "29": "SaveVideo"}
            for node in ("15", "24"):
                sampler = {"current_node": node, "value": 1.0, "step": 8, "steps": 8,
                           "nodes_total": 0, "nodes_done": 0}
                runner.apply_event(record, "generate", "progress", sampler)
            # a finished sampler is not a finished generation: the decode and the save are still to come
            self.assertAlmostEqual(record["stages"][0]["progress"], 48 / 62, places=6)
            self.assertLess(record["stages"][0]["progress"], 1)
            self.assertGreater(record["progress"], 0.3)
            self.assertLess(record["progress"], 0.85)
            self.assertEqual(record["message"], "Generating video: step 8 of 8")
            # the fraction ComfyUI reports counts only the nodes that started, so it says 1.0 almost at once: it is ignored
            overall = {"current_node": "26", "value": 1.0, "step": None, "steps": None,
                       "nodes_total": 3, "nodes_done": 2}
            runner.apply_event(record, "generate", "progress", overall)
            self.assertAlmostEqual(record["stages"][0]["progress"], 48 / 62, places=6)
            self.assertLess(record["stages"][0]["progress"], 1)


if __name__ == "__main__":
    unittest.main()
