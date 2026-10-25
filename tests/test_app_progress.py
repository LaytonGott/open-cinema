import unittest

from app import progress


class ProgressTests(unittest.TestCase):
    def test_generation(self):
        self.assertAlmostEqual(progress.generation_progress(0.5), 0.425, places=9)
        self.assertAlmostEqual(progress.generation_progress(2), 0.85, places=9)
        self.assertEqual(progress.generation_progress(-1), 0)

    def test_optics(self):
        self.assertAlmostEqual(progress.optics_progress(0.5), 0.925, places=9)
        self.assertAlmostEqual(progress.optics_progress(0.5, first_run=False), 0.5, places=9)
        self.assertAlmostEqual(progress.optics_progress(5), 1.0, places=9)

    def test_monotonic(self):
        self.assertEqual(progress.monotonic(0.4, 0.2), 0.4)
        self.assertEqual(progress.monotonic(0.4, 0.6), 0.6)

    def test_messages(self):
        m = progress.message_for_node
        groups = {
            "Loading the LTX-2 models": (
                "UnetLoaderGGUF", "LTXAVTextEncoderLoader", "VAELoader",
                "LTXVAudioVAELoader", "LatentUpscaleModelLoader", "CLIPTextEncode"),
            "Generating video": ("SamplerCustomAdvanced",),
            "Upscaling the video": ("LTXVLatentUpsampler",),
            "Decoding the video": ("VAEDecodeTiled", "LTXVAudioVAEDecode"),
            "Reading the video": ("LoadVideo", "GetVideoComponents"),
            "Estimating depth": ("LoadDA3Model", "DA3Inference", "DA3Render"),
            "Scaling depth to metres": (
                "OpenOptics_DepthToMetric", "OpenOptics_DepthTemporalSmooth"),
            "Applying depth of field": ("OpenOptics_DepthOfField",),
            "Saving the video": ("CreateVideo", "SaveVideo"),
        }
        for text, types in groups.items():
            for class_type in types:
                for stage in ("generate", "optics"):
                    self.assertEqual(m(stage, class_type), text, class_type)

    def test_steps(self):
        m = progress.message_for_node
        self.assertEqual(m("generate", "SamplerCustomAdvanced", 3, 20), "Generating video: step 3 of 20")
        self.assertEqual(m("generate", "SamplerCustomAdvanced", 3, None), "Generating video")
        self.assertEqual(m("generate", "SamplerCustomAdvanced", None, 20), "Generating video")

    def test_unknown_type(self):
        m = progress.message_for_node
        self.assertEqual(m("generate", "Other", previous="Decoding the video"), "Decoding the video")
        self.assertEqual(m("optics", None, previous="Saving the video"), "Saving the video")
        self.assertEqual(m("generate", "Other", previous="Waiting for ComfyUI"), "Generating video")
        self.assertEqual(m("optics", "Other", previous="Waiting for ComfyUI"), "Estimating depth")
        self.assertEqual(m("generate", "Other"), "Generating video")
        self.assertEqual(m("optics", None), "Estimating depth")


if __name__ == "__main__":
    unittest.main()
