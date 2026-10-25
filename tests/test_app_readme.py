"""Checks that README.md has a complete "Run the director app" section."""

import re
import unittest
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def _section() -> str:
    """Return the README text under the 'Run the director app' heading, up to the next heading of the same or higher level."""
    lines = README.read_text(encoding="utf-8").splitlines()
    start = level = None
    for i, line in enumerate(lines):
        m = re.match(r"^(#{2,3}) (.*)", line)
        if m and "Run the director app" in m.group(2):
            start, level = i, len(m.group(1))
            break
    if start is None:
        raise AssertionError("no heading containing 'Run the director app'")
    out = []
    in_fence = False
    for line in lines[start + 1:]:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = re.match(r"^(#+) ", line)
        if not in_fence and m and len(m.group(1)) <= level:
            break
        out.append(line)
    return "\n".join(out)


class ReadmeAppSectionTest(unittest.TestCase):
    def test_seven_numbered_steps(self):
        numbers = [int(m.group(1)) for m in re.finditer(r"^(\d+)\. ", _section(), re.M)]
        self.assertGreaterEqual(len(numbers), 7)
        self.assertEqual(numbers[:7], [1, 2, 3, 4, 5, 6, 7])

    def test_start_command_in_code_block(self):
        blocks = re.findall(r"```[^\n]*\n(.*?)```", _section(), re.S)
        self.assertTrue(any("python -m app" in b for b in blocks))

    def test_step_one_files_and_folders(self):
        section = _section()
        for text in ("v0.41", "ComfyUI-GGUF", "LoadDA3Model", "DA3Inference", "DA3Render",
                     "custom_nodes", "docs/benchmarks.md"):
            self.assertIn(text, section)
        step_one = next(line for line in section.splitlines() if line.startswith("1. "))
        pairs = [
            ("ltx-2-19b-distilled_Q4_K_M.gguf", "models\\diffusion_models"),
            ("gemma_3_12B_it_fp8_scaled.safetensors", "models\\text_encoders"),
            ("ltx-2-19b-embeddings_connector_distill_bf16.safetensors", "models\\checkpoints"),
            ("LTX2_audio_vae_bf16.safetensors", "models\\checkpoints"),
            ("LTX2_video_vae_bf16.safetensors", "models\\vae"),
            ("ltx-2-spatial-upscaler-x2-1.0.safetensors", "models\\latent_upscale_models"),
            ("depth_anything_3_mono_large.safetensors", "models\\geometry_estimation"),
        ]
        for name, folder in pairs:
            self.assertIn(name, step_one)
            self.assertIn(folder, step_one)

    def _step(self, number: int) -> str:
        """Return the text of the top-level numbered item `number` in the section."""
        parts = re.split(r"^(?=\d+\. )", _section(), flags=re.M)
        return next(p for p in parts if p.startswith(f"{number}. "))

    def test_step_two_install(self):
        self.assertIn("pip install -r app/requirements.txt", self._step(2))

    def test_step_three_comfyui(self):
        step = self._step(3)
        for text in ("run_nvidia_gpu.bat", "To see the GUI go to"):
            self.assertIn(text, step)

    def test_step_four_start_app(self):
        step = self._step(4)
        for text in ("python -m app", "npm run app", "--comfyui", "http://127.0.0.1:8188",
                     "http://127.0.0.1:8000"):
            self.assertIn(text, step)

    def test_npm_run_app_and_not_running(self):
        section = _section()
        for text in ("npm run app", "isn't running", "Retry", "python -m app", "--comfyui"):
            self.assertIn(text, section)

    def test_accept_needles_present(self):
        section = _section()
        needles = ("python -m app", "--comfyui", "http://127.0.0.1:8000", "run_nvidia_gpu.bat", "custom_nodes",
                   "ComfyUI-GGUF", "pip install", "comfy-sdk", "comfy-api-proxy", "npm run app",
                   "playwright install chromium", "npm test", "isn't running", "Retry",
                   "ltx-2-19b-distilled_Q4_K_M.gguf", "gemma_3_12B_it_fp8_scaled.safetensors",
                   "ltx-2-19b-embeddings_connector_distill_bf16.safetensors", "LTX2_video_vae_bf16.safetensors",
                   "LTX2_audio_vae_bf16.safetensors", "ltx-2-spatial-upscaler-x2-1.0.safetensors",
                   "depth_anything_3_mono_large.safetensors", "models", "diffusion_models", "text_encoders",
                   "latent_upscale_models", "geometry_estimation")
        for needle in needles:
            with self.subTest(needle=needle):
                self.assertIn(needle, section)

    def test_no_todo(self):
        self.assertNotIn("TODO", _section())


if __name__ == "__main__":
    unittest.main()
