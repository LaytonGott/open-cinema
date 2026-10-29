import json
import re
import unittest
from pathlib import Path

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

    def test_generation_inputs_acceptance(self):
        prompt = "A slow dolly shot through a rainy neon street"
        prefix = "opencinema/test/before"
        graph = build_generation_graph(prompt, 1234, prefix)
        encoders = _nodes(graph, "CLIPTextEncode")
        self.assertEqual(len(encoders), 1)
        self.assertEqual(encoders[0]["inputs"]["text"], prompt)
        noises = _nodes(graph, "RandomNoise")
        self.assertEqual(len(noises), 2)
        self.assertEqual({n["inputs"]["noise_seed"] for n in noises}, {1234, 1612})
        self.assertIn(GENERATION_OUTPUT_NODE, graph)
        out = graph[GENERATION_OUTPUT_NODE]
        self.assertEqual(out["class_type"], "SaveVideo")
        self.assertEqual(out["inputs"]["filename_prefix"], prefix)
        self.assertEqual(len(_nodes(graph, "SaveVideo")), 1)


LORA = "ltx-2-19b-lora-camera-control-dolly-in.safetensors"


class GenerationGraphLoraTests(unittest.TestCase):
    def setUp(self):
        self.plain = build_generation_graph(PROMPT, SEED, PREFIX)
        self.graph = build_generation_graph(PROMPT, SEED, PREFIX, camera_lora=LORA)

    def test_lora_node(self):
        self.assertEqual(self.graph["30"], {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["1", 0], "lora_name": LORA, "strength_model": 1.0}})

    def test_guiders_take_lora_model(self):
        self.assertEqual(self.graph["14"]["inputs"]["model"], ["30", 0])
        self.assertEqual(self.graph["23"]["inputs"]["model"], ["30", 0])

    def test_only_lora_and_guiders_differ(self):
        changed = {k for k in self.graph if self.graph[k] != self.plain.get(k)}
        self.assertEqual(changed, {"14", "23", "30"})

    def test_lora_graph_validates(self):
        self.assertEqual(validate_prompt(self.graph, input_files=[]), [])

    def test_none_is_plain_graph(self):
        self.assertEqual(build_generation_graph(PROMPT, SEED, PREFIX, camera_lora=None), self.plain)
        self.assertNotIn("30", self.plain)


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


class OpticsGraphSettingsTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_optics_graph("clip.webm", 50, 2.8, 5.1005, "p/x")

    def _inputs(self, class_type):
        return _nodes(self.graph, class_type)[0]["inputs"]

    def _check(self, class_type, expected):
        inputs = self._inputs(class_type)
        for key, value in expected.items():
            self.assertEqual(inputs[key], value, f"{class_type}.{key}")

    def test_load_model(self):
        self._check("LoadDA3Model", {"model_name": "depth_anything_3_mono_large.safetensors", "weight_dtype": "default"})

    def test_inference(self):
        self._check("DA3Inference", {"resolution": 504, "resize_method": "upper_bound_resize", "mode": "mono"})

    def test_render(self):
        self._check("DA3Render", {"output": "depth", "output.normalization": "raw", "output.apply_sky_clip": False})

    def test_depth_to_metric(self):
        self._check("OpenOptics_DepthToMetric", {
            "mode": "subject", "subject_x": 0.5, "subject_y": 0.5, "near_m": 0.3, "far_m": 80,
            "low_percentile": 2, "high_percentile": 98, "inverse_depth": False})

    def test_temporal_smooth(self):
        self._check("OpenOptics_DepthTemporalSmooth", {"strength": 0.7})

    def test_depth_of_field(self):
        self._check("OpenOptics_DepthOfField", {
            "sensor_width_mm": 36, "max_radius_px": 24, "quality": "normal", "colorspace": "srgb"})


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


class OpticsGraphChangedNodesTests(unittest.TestCase):
    def test_aperture_lens_distance_only_in_expected_nodes(self):
        def differing(a, b):
            self.assertEqual(set(a), set(b))
            return sorted(k for k in a if a[k] != b[k])

        base = build_optics_graph("clip.webm", 50, 2.8, 5.1005, "p/x")
        dof_id = next(k for k, n in base.items() if n["class_type"] == "OpenOptics_DepthOfField")
        metric_id = next(k for k, n in base.items() if n["class_type"] == "OpenOptics_DepthToMetric")

        aperture = build_optics_graph("clip.webm", 50, 4, 5.1005, "p/x")
        self.assertEqual(differing(base, aperture), [dof_id])
        lens = build_optics_graph("clip.webm", 85, 2.8, 5.1005, "p/x")
        self.assertEqual(differing(base, lens), [dof_id])
        distance = build_optics_graph("clip.webm", 50, 2.8, 8.6709, "p/x")
        self.assertEqual(differing(base, distance), sorted([metric_id, dof_id]))


def _single(graph, class_type):
    found = [(k, n["inputs"]) for k, n in graph.items() if n["class_type"] == class_type]
    assert len(found) == 1, class_type
    return found[0]


class OpticsGraphWiringTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_optics_graph("clip.webm", 50, 2.8, 5.1005, "p/x")

    def test_dof_and_smooth_links(self):
        g = self.graph
        components_id, _ = _single(g, "GetVideoComponents")
        render_id, _ = _single(g, "DA3Render")
        metric_id, metric = _single(g, "OpenOptics_DepthToMetric")
        smooth_id, smooth = _single(g, "OpenOptics_DepthTemporalSmooth")
        dof_id, dof = _single(g, "OpenOptics_DepthOfField")
        self.assertEqual(dof["image"], [components_id, 0])
        self.assertEqual(dof["depth_mask"], [smooth_id, 0])
        self.assertEqual(smooth["depth"], [metric_id, 0])
        self.assertEqual(metric["depth_image"], [render_id, 0])
        self.assertEqual(
            (components_id, smooth_id, metric_id, render_id, dof_id),
            ("2", "7", "6", "5", "8"),
        )

    def test_video_links(self):
        g = self.graph
        components_id, _ = _single(g, "GetVideoComponents")
        dof_id, _ = _single(g, "OpenOptics_DepthOfField")
        create_id, create = _single(g, "CreateVideo")
        _, save = _single(g, "SaveVideo")
        self.assertEqual(create["images"], [dof_id, 0])
        self.assertEqual(create["audio"], [components_id, 1])
        self.assertEqual(create["fps"], [components_id, 2])
        self.assertEqual(save["video"], [create_id, 0])
        self.assertEqual(create_id, "9")


class GenerationStageTests(unittest.TestCase):
    def test_stage_and_step_counts(self):
        g = build_generation_graph("a prompt", 7, "p/x")
        for class_type in ("SamplerCustomAdvanced", "RandomNoise", "ManualSigmas", "CFGGuider"):
            self.assertEqual(len(_nodes(g, class_type)), 2, class_type)
        samplers = sorted(k for k, n in g.items() if n["class_type"] == "SamplerCustomAdvanced")
        self.assertEqual(samplers, ["15", "24"])
        self.assertEqual(g["15"]["inputs"]["sigmas"], ["13", 0])
        self.assertEqual(len(g["13"]["inputs"]["sigmas"].split(",")), 9)
        self.assertEqual(g["24"]["inputs"]["sigmas"], ["22", 0])
        self.assertEqual(len(g["22"]["inputs"]["sigmas"].split(",")), 4)

    def test_stage_two_uses_upsampled_latent(self):
        g = build_generation_graph("a prompt", 7, "p/x")
        self.assertEqual(g["24"]["inputs"]["latent_image"], ["19", 0])
        self.assertEqual(g["19"]["class_type"], "LTXVConcatAVLatent")
        self.assertEqual(g["19"]["inputs"]["video_latent"], ["18", 0])
        self.assertEqual(g["18"]["class_type"], "LTXVLatentUpsampler")
        self.assertEqual(g["18"]["inputs"]["samples"], ["16", 0])
        self.assertEqual(g["16"]["class_type"], "LTXVSeparateAVLatent")
        self.assertEqual(g["16"]["inputs"]["av_latent"], ["15", 1])

    def test_noise_seeds(self):
        g = build_generation_graph("a prompt", 7, "p/x")
        first = g["15"]["inputs"]["noise"][0]
        self.assertEqual(first, "11")
        self.assertEqual(g[first]["class_type"], "RandomNoise")
        self.assertEqual(g[first]["inputs"]["noise_seed"], 7)
        second = g["24"]["inputs"]["noise"][0]
        self.assertEqual(second, "20")
        self.assertEqual(g[second]["class_type"], "RandomNoise")
        self.assertEqual(g[second]["inputs"]["noise_seed"], 385)


class GenerationGraphSeedTests(unittest.TestCase):
    def test_seed_only_changes_noise_nodes(self):
        a = build_generation_graph(PROMPT, 1, PREFIX)
        b = build_generation_graph(PROMPT, 2, PREFIX)
        self.assertEqual(set(a), set(b))
        differing = {k for k in a if a[k] != b[k]}
        noise = {k for k, n in a.items() if n["class_type"] == "RandomNoise"}
        self.assertEqual(len(noise), 2)
        self.assertEqual(differing, noise)
        self.assertEqual(a, build_generation_graph(PROMPT, 1, PREFIX))

    def test_prompt_and_prefix_only_change_their_nodes(self):
        a = build_generation_graph(PROMPT, SEED, PREFIX)
        b = build_generation_graph("A static wide shot of a desert road", SEED, "opencinema/test/after")
        self.assertEqual(set(a), set(b))
        differing = {k for k in a if a[k] != b[k]}
        text = {k for k, n in a.items() if n["class_type"] == "CLIPTextEncode"}
        self.assertEqual(differing, text | {GENERATION_OUTPUT_NODE})


class NoBenchImportTests(unittest.TestCase):
    def test_app_does_not_import_bench(self):
        app_dir = Path(__file__).resolve().parent.parent / "app"
        for path in app_dir.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(
                re.search(r"^\s*(from|import)\s+bench\b", text, re.M),
                f"{path.name} imports bench",
            )


if __name__ == "__main__":
    unittest.main()
