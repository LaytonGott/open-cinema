"""map_error: ComfyError HTTP statuses and codes."""

import unittest

from comfy_sdk.exceptions import ComfyError

from app.errors import DOWNLOAD_MESSAGE, INTERNAL_MESSAGE, UNREACHABLE_MESSAGE, map_error


class ErrorStatusTest(unittest.TestCase):
    def test_gateway_statuses_are_unreachable(self):
        for status in (502, 503, 504):
            with self.subTest(status=status):
                got = map_error(ComfyError("x", http_status=status), "generate")
                self.assertEqual(
                    got, {"code": "comfy_unreachable", "message": UNREACHABLE_MESSAGE, "stage": "generate"}
                )

    def test_output_unavailable_is_download_failed(self):
        exc = ComfyError("x", code="output_unavailable", http_status=404)
        got = map_error(exc, "generate")
        self.assertEqual(got, {"code": "download_failed", "message": DOWNLOAD_MESSAGE, "stage": "generate"})

    def test_404_with_output_unavailable_text_is_download_failed(self):
        got = map_error(ComfyError("output_unavailable", http_status=404), "optics")
        self.assertEqual(got["code"], "download_failed")

    def test_other_comfy_error_is_internal(self):
        got = map_error(ComfyError("x", code="boom", http_status=500), "generate")
        self.assertEqual(got, {"code": "internal", "message": INTERNAL_MESSAGE, "stage": "generate"})

    def test_stage_is_passed_through(self):
        self.assertEqual(map_error(ComfyError("x", http_status=503), "optics")["stage"], "optics")


if __name__ == "__main__":
    unittest.main()
