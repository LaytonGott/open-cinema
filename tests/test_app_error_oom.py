"""Tests for the plain out-of-memory message in app.errors.map_error."""

import unittest

from comfy_low.models import JobError
from comfy_sdk.exceptions import JobFailed

from app.errors import map_error

SENTENCE = "ComfyUI ran out of memory. Close other programs that use the GPU or memory, then retry."


def _failed(text):
    error = JobError(code="node_execution_error", message=text, node_id="7", class_type="DA3Inference")
    return map_error(JobFailed("job failed", error=error), "optics")


class OutOfMemoryTests(unittest.TestCase):
    def check_oom(self, text):
        result = _failed(text)
        self.assertEqual(result["code"], "job_failed")
        self.assertTrue(result["message"].startswith(SENTENCE))
        self.assertIn("DA3Inference", result["message"])
        self.assertIn(text, result["message"])

    def test_allocation_on_device(self):
        self.check_oom("Allocation on device")

    def test_cuda_out_of_memory(self):
        self.check_oom("CUDA out of memory")

    def test_paging_file(self):
        self.check_oom("The paging file is too small (error 1455)")

    def test_unrelated_failure_has_no_sentence(self):
        result = _failed("shape mismatch")
        self.assertEqual(result["code"], "job_failed")
        self.assertNotIn(SENTENCE, result["message"])


if __name__ == "__main__":
    unittest.main()
