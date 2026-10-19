"""Real-clip benchmark skeleton: skipped unless the benchmark fixture and CUDA are present."""
import os
import re
import tempfile
import unittest

import torch

DEFAULT_FIXTURE_DIR = r"D:\OpenCinema\fixtures\real_clip"
FIXTURE_FILES = ("frames_u8.npy", "depth_u8.npy", "subject_mask_u8.npy")


def missing_reason(fixture_dir=None):
    """Return None if the real-clip fixture and CUDA are available, else a string saying what is missing.

    fixture_dir is a folder path; default is OPEN_OPTICS_FIXTURE_DIR (read on each call), else
    D:\\OpenCinema\\fixtures\\real_clip. Only reads; never copies or writes the fixture.
    """
    if fixture_dir is None:
        fixture_dir = os.environ.get("OPEN_OPTICS_FIXTURE_DIR", DEFAULT_FIXTURE_DIR)
    missing = [n for n in FIXTURE_FILES if not os.path.isfile(os.path.join(fixture_dir, n))]
    if missing:
        return (f"real clip fixture folder {fixture_dir} is missing {', '.join(missing)}; "
                "set OPEN_OPTICS_FIXTURE_DIR to the folder that holds them")
    if not torch.cuda.is_available():
        return "CUDA is not available"
    return None


def parse_layers(message):
    """Return the integer after ' layers=' in an open_optics_nodes log message (a count, unitless).

    Raises ValueError if the message has no ' layers=<n>' field.
    """
    match = re.search(r" layers=(\d+)", message)
    if match is None:
        raise ValueError(f"no layers= field in log message: {message!r}")
    return int(match.group(1))


def run_chain(fixture_dir):
    """Run Depth to Metric, Temporal Smooth and Depth of Field on the real clip in fixture_dir (CUDA).

    Returns a dict: metric_s, smooth_s, dof_s (seconds per node call), layers (count from the last
    Depth of Field log message), peak_gib (peak GPU memory of the chain, GiB) and output (the Depth of
    Field image tensor, float32 [B, H, W, C] on the CPU). Only reads the fixture.
    """
    import logging
    import time
    from unittest import mock

    import numpy as np

    import open_optics_nodes

    frames = torch.from_numpy(np.load(os.path.join(fixture_dir, "frames_u8.npy"))).float().div_(255.0).contiguous()
    depth = torch.from_numpy(np.load(os.path.join(fixture_dir, "depth_u8.npy"))).float().div_(255.0).contiguous()
    mask = torch.from_numpy(np.load(os.path.join(fixture_dir, "subject_mask_u8.npy"))).float().div_(255.0).contiguous()

    messages = []

    class Collect(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    def call(key, **kw):
        cls = open_optics_nodes.NODE_CLASS_MAPPINGS[key]
        start = time.perf_counter()
        out = getattr(cls(), cls.FUNCTION)(**kw)
        torch.cuda.synchronize()
        return out, time.perf_counter() - start

    settings = dict(focal_mm=50.0, f_number=1.8, focus_m=2.0, sensor_width_mm=36.0,
                    quality="normal", max_radius_px=24, colorspace="srgb")
    logger = logging.getLogger("open_optics_nodes")
    handler = Collect(level=logging.INFO)
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        with mock.patch.dict(os.environ, {"OPEN_OPTICS_DEVICE": "cuda"}):
            call("OpenOptics_DepthOfField", image=frames[:2].clone(),
                 depth_mask=(depth[:2] * 5 + 1).clone(), **settings)
            torch.cuda.reset_peak_memory_stats()
            out, metric_s = call("OpenOptics_DepthToMetric", depth_mask=depth, subject_mask=mask,
                                 mode="subject", subject_m=2.0, anchor_scope="frame",
                                 inverse_depth=True, near_m=0.3, far_m=500.0)
            metric = out[0]
            out, smooth_s = call("OpenOptics_DepthTemporalSmooth", depth=metric, strength=0.7)
            smooth = out[0]
            del messages[:]
            out, dof_s = call("OpenOptics_DepthOfField", image=frames, depth_mask=smooth, **settings)
            peak_gib = torch.cuda.max_memory_allocated() / 1024 ** 3
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    dof_messages = [m for m in messages if "node=OpenOptics_DepthOfField" in m]
    return {"metric_s": metric_s, "smooth_s": smooth_s, "dof_s": dof_s,
            "layers": parse_layers(dof_messages[-1]), "peak_gib": peak_gib, "output": out[0]}


@unittest.skipUnless(os.environ.get("OPEN_OPTICS_BENCH") == "1", "set by npm run test:bench")
class TestBenchReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reason = missing_reason()
        if reason is not None:
            raise unittest.SkipTest(reason)

    last_result = None

    def tearDown(self):
        torch.cuda.empty_cache()

    def test_bench_real_clip(self):
        import numpy as np

        fixture_dir = os.environ.get("OPEN_OPTICS_FIXTURE_DIR", DEFAULT_FIXTURE_DIR)
        in_shape = tuple(np.load(os.path.join(fixture_dir, "frames_u8.npy"), mmap_mode="r").shape)
        result = run_chain(fixture_dir)
        type(self).last_result = result
        print(f"metric_s={result['metric_s']:.3f} smooth_s={result['smooth_s']:.3f} "
              f"dof_s={result['dof_s']:.3f} layers={result['layers']} peak_gib={result['peak_gib']:.3f}")
        out = result["output"]
        self.assertLess(result["dof_s"], 20)
        self.assertLess(result["smooth_s"], 6)
        self.assertLess(result["metric_s"], 10)
        self.assertLess(result["peak_gib"], 8)
        self.assertLessEqual(result["layers"], 12)
        self.assertTrue(torch.isfinite(out).all().item())
        self.assertEqual(out.dtype, torch.float32)
        self.assertEqual(out.device.type, "cpu")
        self.assertEqual(tuple(out.shape), in_shape)


class TestMissingReason(unittest.TestCase):
    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            reason = missing_reason(d)
        self.assertIn("frames_u8.npy", reason)
        self.assertIn(d, reason)
        self.assertIn("OPEN_OPTICS_FIXTURE_DIR", reason)

    def test_all_files_present(self):
        with tempfile.TemporaryDirectory() as d:
            for n in FIXTURE_FILES:
                open(os.path.join(d, n), "wb").close()
            reason = missing_reason(d)
        self.assertTrue(reason is None or "CUDA" in reason)


class TestParseLayers(unittest.TestCase):
    def test_parse_layers_known_line(self):
        line = ("node=OpenOptics_DepthOfField device=cuda:0 frames=2 chunk_frames=2 "
                "seconds=1.234 layers=7")
        self.assertEqual(parse_layers(line), 7)

    def test_parse_layers_missing(self):
        line = "node=OpenOptics_DepthOfField device=cuda:0 frames=2 chunk_frames=2 seconds=1.234"
        with self.assertRaises(ValueError):
            parse_layers(line)


if __name__ == "__main__":
    unittest.main()
