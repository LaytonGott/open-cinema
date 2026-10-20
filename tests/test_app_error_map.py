"""Tests for app.errors.map_error: one case per error code."""

import unittest

import httpx
from comfy_low.models import JobError
from comfy_sdk.exceptions import InvalidWorkflow, JobFailed

from app.errors import ComfyUnreachable, map_error


class MapErrorTests(unittest.TestCase):
    def test_invalid_workflow_is_comfy_rejected(self):
        exc = InvalidWorkflow("Value not in list: unet_name", code="invalid_workflow")
        result = map_error(exc, "generate")
        self.assertEqual(result["code"], "comfy_rejected")
        self.assertEqual(result["stage"], "generate")
        self.assertIn("Value not in list: unet_name", result["message"])

    def test_invalid_workflow_passes_optics_stage_through(self):
        result = map_error(InvalidWorkflow("bad graph"), "optics")
        self.assertEqual(result["code"], "comfy_rejected")
        self.assertEqual(result["stage"], "optics")

    def test_job_failed_is_job_failed_with_node_and_message(self):
        error = JobError(
            code="node_execution_error",
            message="CUDA out of memory",
            node_id="7",
            class_type="DA3Inference",
        )
        result = map_error(JobFailed("job failed", error=error), "optics")
        self.assertEqual(result["code"], "job_failed")
        self.assertEqual(result["stage"], "optics")
        self.assertIn("DA3Inference", result["message"])
        self.assertIn("CUDA out of memory", result["message"])

    def test_httpx_connect_error_is_comfy_unreachable(self):
        result = map_error(httpx.ConnectError("refused"), "generate")
        self.assertEqual(result["code"], "comfy_unreachable")
        self.assertEqual(result["stage"], "generate")

    def test_comfy_unreachable_is_comfy_unreachable(self):
        result = map_error(ComfyUnreachable("health check failed"), "optics")
        self.assertEqual(result["code"], "comfy_unreachable")
        self.assertEqual(result["stage"], "optics")

    def test_lookup_error_is_download_failed(self):
        result = map_error(LookupError("no video output"), "generate")
        self.assertEqual(result["code"], "download_failed")
        self.assertEqual(result["stage"], "generate")

    def test_other_exception_is_internal_without_its_text(self):
        result = map_error(RuntimeError("secret"), "generate")
        self.assertEqual(result["code"], "internal")
        self.assertEqual(result["stage"], "generate")
        self.assertNotIn("secret", result["message"])


if __name__ == "__main__":
    unittest.main()
