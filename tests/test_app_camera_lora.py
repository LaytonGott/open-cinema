"""Backend test of the LTX-2 camera LoRAs at shot creation (docs/app-spec.md 7.3), against the fake ComfyUI."""
import copy
import unittest

from tests.app_harness import SHOT, AppHarness

LOADER = "LoraLoaderModelOnly"
JIB_UP = "ltx-2-19b-lora-camera-control-jib-up.safetensors"
STATIC = "ltx-2-19b-lora-camera-control-static.safetensors"


def generation_graph(fake, since):
    """Return the last generation graph (the one with a SamplerCustomAdvanced) ComfyUI got after prompt index `since`."""
    found = [g for g in fake.prompts[since:]
             if any(n.get("class_type") == "SamplerCustomAdvanced" for n in g.values())]
    return found[-1] if found else None


class CameraLoraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = AppHarness(delay=0.02).start()
        cls.fake = cls.harness.fake
        cls.saved = copy.deepcopy(cls.fake.object_info[LOADER])

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()

    def tearDown(self):
        self.fake.object_info[LOADER] = copy.deepcopy(self.saved)

    def make(self, camera, seed):
        mark = len(self.fake.prompts)
        status, record = self.harness.post("/api/shots", {**SHOT, "camera": camera, "seed": seed})
        self.assertEqual(status, 201, record)
        done = self.harness.wait_for_shot(record["id"], "done", timeout=60)
        return record, done, generation_graph(self.fake, mark)

    def test_listed_lora_is_used(self):
        record, done, graph = self.make("crane-up", 11)
        self.assertEqual(record["derived"]["camera_control"], "lora")
        self.assertEqual(done["derived"]["camera_control"], "lora")
        self.assertEqual(graph["30"]["inputs"]["lora_name"], JIB_UP)
        self.assertEqual(graph["14"]["inputs"]["model"], ["30", 0])

    def test_move_without_lora_uses_prompt(self):
        _, done, graph = self.make("handheld", 12)
        self.assertEqual(done["derived"]["camera_control"], "prompt")
        self.assertNotIn("30", graph)

    def test_unlisted_file_falls_back(self):
        self.fake.object_info[LOADER]["input"]["required"]["lora_name"] = [[STATIC]]
        _, done, graph = self.make("dolly-out", 13)
        self.assertEqual(done["derived"]["camera_control"], "prompt")
        self.assertNotIn("30", graph)
        _, done, graph = self.make("static", 14)
        self.assertEqual(done["derived"]["camera_control"], "lora")
        self.assertEqual(graph["30"]["inputs"]["lora_name"], STATIC)

    def test_missing_loader_falls_back(self):
        self.fake.remove_node(LOADER)
        _, done, graph = self.make("truck-right", 15)
        self.assertEqual(done["derived"]["camera_control"], "prompt")
        self.assertNotIn("30", graph)


if __name__ == "__main__":
    unittest.main()
