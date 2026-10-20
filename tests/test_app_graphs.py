import json
import unittest

from app.graphs import GENERATION_OUTPUT_NODE, build_generation_graph
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


if __name__ == "__main__":
    unittest.main()
