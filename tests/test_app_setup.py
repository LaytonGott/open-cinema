import unittest

from app import setup


class ModelsTableTest(unittest.TestCase):
    def test_models_table(self):
        models = setup.MODELS
        self.assertEqual(len(models), 14)
        self.assertEqual(models[0]["name"], "ltx-2-19b-distilled_Q4_K_M.gguf")
        self.assertEqual(models[0]["folder"], "diffusion_models")
        self.assertEqual(models[0]["size"], 12651789536)
        self.assertEqual(sum(1 for m in models if m["required"]), 7)
        self.assertTrue(all(m["required"] for m in models[:7]))

        by_name = {m["name"]: m for m in models}
        dolly = by_name["ltx-2-19b-lora-camera-control-dolly-in.safetensors"]
        self.assertEqual(
            dolly["url"],
            "https://huggingface.co/Lightricks/LTX-2-19b-LoRA-Camera-Control-Dolly-In/resolve/main/"
            "ltx-2-19b-lora-camera-control-dolly-in.safetensors")
        self.assertEqual(dolly["size"], 327309208)
        jib = by_name["ltx-2-19b-lora-camera-control-jib-up.safetensors"]
        self.assertEqual(
            jib["url"],
            "https://huggingface.co/Lightricks/LTX-2-19b-LoRA-Camera-Control-Jib-Up/resolve/main/"
            "ltx-2-19b-lora-camera-control-jib-up.safetensors")
        self.assertEqual(jib["size"], 2214978664)


if __name__ == "__main__":
    unittest.main()
