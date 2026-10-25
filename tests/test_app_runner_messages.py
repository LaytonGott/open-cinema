import tempfile
import unittest

from app import graphs
from app.record import new_record
from app.runner import ShotRunner
from app.store import ShotStore

PARAMS = {"description": "A woman walks.", "camera": "dolly-in", "lens_mm": 50,
          "aperture": 2.8, "framing": "full-body", "seed": 123}


def types_of(graph):
    return {k: v["class_type"] for k, v in graph.items()}


def id_of(graph, class_type):
    return next(k for k, v in graph.items() if v["class_type"] == class_type)


class RunnerMessagesTest(unittest.TestCase):
    def make(self, tmp, graph):
        store = ShotStore(tmp)
        record = store.add(new_record("abc", PARAMS))
        runner = ShotRunner(store)
        runner.graph_types[record["id"]] = types_of(graph)
        return runner, record

    def progress(self, runner, record, stage, node, **extra):
        frame = {"current_node": node, "value": 0.1, "step": 0, "steps": 0, "nodes_total": 1}
        frame.update(extra)
        runner.apply_event(record, stage, "progress", frame)
        return record["message"]

    def test_generate_node_ids_give_messages_in_order(self):
        graph = graphs.build_generation_graph("p", 1, "x")
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp, graph)
            seen = [
                self.progress(runner, record, "generate", "1"),
                self.progress(runner, record, "generate", "4"),
                self.progress(runner, record, "generate", "15", nodes_total=0, step=3, steps=8),
                self.progress(runner, record, "generate", "18"),
                self.progress(runner, record, "generate", "26"),
                self.progress(runner, record, "generate", "28"),
            ]
            self.assertEqual(seen, [
                "Loading the LTX-2 models", "Loading the LTX-2 models",
                "Generating video: step 3 of 8", "Upscaling the video",
                "Decoding the video", "Saving the video"])

    def test_unknown_node_id_keeps_previous_message(self):
        graph = graphs.build_generation_graph("p", 1, "x")
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp, graph)
            before = self.progress(runner, record, "generate", "18")
            self.assertEqual(before, "Upscaling the video")
            self.assertEqual(self.progress(runner, record, "generate", "999"), before)

    def test_optics_node_ids_give_messages(self):
        graph = graphs.build_optics_graph("v.mp4", 50, 2.8, 3.0, "x")
        with tempfile.TemporaryDirectory() as tmp:
            runner, record = self.make(tmp, graph)
            expected = [
                ("LoadVideo", "Reading the video"),
                ("DA3Inference", "Estimating depth"),
                ("OpenOptics_DepthToMetric", "Scaling depth to metres"),
                ("OpenOptics_DepthOfField", "Applying depth of field"),
            ]
            for class_type, message in expected:
                self.assertEqual(
                    self.progress(runner, record, "optics", id_of(graph, class_type)), message)


if __name__ == "__main__":
    unittest.main()
