import json
import unittest

from app.graphs import (
    GENERATION_OUTPUT_NODE,
    OPTICS_OUTPUT_NODE,
    build_generation_graph,
    build_optics_graph,
)
from tests.fake_comfy import validate_prompt

PROMPT = "A slow dolly shot through a rainy neon street"
SEED = 1234
PREFIX = "opencinema/test/before"


def _nodes(graph, class_type):
    return [n for n in graph.values() if n["class_type"] == class_type]


class BuildGenerationGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_generation_graph(PROMPT, SEED, PREFIX)

    def test_validates_without_problems(self):
        self.assertEqual(validate_prompt(self.graph, input_files=[]), [])

    def test_json_serialisable(self):
        self.assertIsInstance(json.dumps(self.graph), str)

    def test_node_counts(self):
        self.assertEqual(len(_nodes(self.graph, "SamplerCustomAdvanced")), 2)
        self.assertEqual(len(_nodes(self.graph, "LTXVLatentUpsampler")), 1)
        self.assertEqual(len(_nodes(self.graph, "SaveVideo")), 1)
        self.assertEqual(len(_nodes(self.graph, "CLIPTextEncode")), 1)

    def test_first_stage_latent_size(self):
        inputs = _nodes(self.graph, "EmptyLTXVLatentVideo")[0]["inputs"]
        self.assertEqual(inputs["width"], 640)
        self.assertEqual(inputs["height"], 352)
        self.assertEqual(inputs["length"], 121)

    def test_unet_name(self):
        inputs = _nodes(self.graph, "UnetLoaderGGUF")[0]["inputs"]
        self.assertEqual(inputs["unet_name"], "ltx-2-19b-distilled_Q4_K_M.gguf")

    def test_prompt_seed_and_prefix(self):
        self.assertEqual(_nodes(self.graph, "CLIPTextEncode")[0]["inputs"]["text"], PROMPT)
        seeds = {n["inputs"]["noise_seed"] for n in _nodes(self.graph, "RandomNoise")}
        self.assertEqual(seeds, {1234, 1612})
        out = self.graph[GENERATION_OUTPUT_NODE]
        self.assertEqual(out["class_type"], "SaveVideo")
        self.assertEqual(out["inputs"]["filename_prefix"], PREFIX)

    def test_deterministic(self):
        self.assertEqual(self.graph, build_generation_graph(PROMPT, SEED, PREFIX))


OPTICS_PREFIX = "opencinema/test/after_1"
OPTICS_CLASS_TYPES = [
    "LoadVideo",
    "GetVideoComponents",
    "LoadDA3Model",
    "DA3Inference",
    "DA3Render",
    "OpenOptics_DepthToMetric",
    "OpenOptics_DepthTemporalSmooth",
    "OpenOptics_DepthOfField",
    "CreateVideo",
    "SaveVideo",
]


class BuildOpticsGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_optics_graph("clip.webm", 50, 2.8, 5.1005, OPTICS_PREFIX)

    def test_validates_without_problems(self):
        self.assertEqual(validate_prompt(self.graph, input_files=["clip.webm"]), [])

    def test_json_serialisable(self):
        self.assertIsInstance(json.dumps(self.graph), str)

    def test_each_class_type_once(self):
        self.assertEqual(len(self.graph), 10)
        for class_type in OPTICS_CLASS_TYPES:
            self.assertEqual(len(_nodes(self.graph, class_type)), 1, class_type)

    def test_output_node_and_prefix(self):
        out = self.graph[OPTICS_OUTPUT_NODE]
        self.assertEqual(out["class_type"], "SaveVideo")
        self.assertEqual(out["inputs"]["filename_prefix"], OPTICS_PREFIX)


class OpticsGraphValuesTests(unittest.TestCase):
    def _check(self, video, focal, f_number, subject, prefix):
        graph = build_optics_graph(video, focal, f_number, subject, prefix)
        self.assertEqual(_nodes(graph, "LoadVideo")[0]["inputs"]["file"], video)
        dof = _nodes(graph, "OpenOptics_DepthOfField")[0]["inputs"]
        self.assertEqual(dof["focal_mm"], focal)
        self.assertEqual(dof["f_number"], f_number)
        self.assertEqual(dof["focus_m"], subject)
        metric = _nodes(graph, "OpenOptics_DepthToMetric")[0]["inputs"]
        self.assertEqual(metric["subject_m"], subject)
        out = graph[OPTICS_OUTPUT_NODE]
        self.assertEqual(out["class_type"], "SaveVideo")
        self.assertEqual(out["inputs"]["filename_prefix"], prefix)

    def test_first_values(self):
        self._check("clip.webm", 50.0, 2.8, 5.1005, "opencinema/test/after_1")

    def test_other_values(self):
        self._check("other.webm", 35, 8, 3.2, "p/x")


class OpticsGraphCacheTests(unittest.TestCase):
    def setUp(self):
        self.g1 = build_optics_graph("clip.webm", 50, 2.8, 5.1005, "opencinema/test/after_1")
        self.g2 = build_optics_graph("clip.webm", 50, 8, 5.1005, "opencinema/test/after_2")

    def test_only_expected_nodes_change(self):
        self.assertEqual(set(self.g1), set(self.g2))
        changed = {
            self.g1[k]["class_type"] for k in self.g1 if self.g1[k] != self.g2[k]
        }
        self.assertLessEqual(changed, {"OpenOptics_DepthOfField", "CreateVideo", "SaveVideo"})
        self.assertIn("OpenOptics_DepthOfField", changed)

    def test_same_arguments_equal_graphs(self):
        again = build_optics_graph("clip.webm", 50, 2.8, 5.1005, "opencinema/test/after_1")
        self.assertEqual(self.g1, again)

    def test_both_graphs_valid(self):
        for graph in (self.g1, self.g2):
            self.assertEqual(validate_prompt(graph, input_files=["clip.webm"]), [])


if __name__ == "__main__":
    unittest.main()
