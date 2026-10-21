import unittest

from tests.app_harness import AppHarness
from tests.fake_comfy import FakeComfy


class ErrorFormatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def assert_error(self, status, body, expected_status, expected_code):
        self.assertEqual(status, expected_status)
        self.assertIsInstance(body, dict)
        self.assertEqual(set(body), {"error"})
        error = body["error"]
        self.assertEqual(set(error), {"code", "message", "field"})
        self.assertEqual(error["code"], expected_code)
        message = error["message"]
        self.assertIsInstance(message, str)
        self.assertTrue(message.endswith((".", "!")), message)
        self.assertNotIn("Traceback", message)

    def test_get_unknown_shot(self):
        status, body = self.harness.get("/api/shots/nope")
        self.assert_error(status, body, 404, "not_found")

    def test_delete_unknown_shot(self):
        status, body = self.harness.request("DELETE", "/api/shots/nope")
        self.assert_error(status, body, 404, "not_found")

    def test_cancel_unknown_shot(self):
        status, body = self.harness.post("/api/shots/nope/cancel")
        self.assert_error(status, body, 404, "not_found")

    def test_reapply_unknown_shot(self):
        status, body = self.harness.post("/api/shots/nope/reapply", {"aperture": 5.6})
        self.assert_error(status, body, 404, "not_found")

    def test_estimate_invalid_lens(self):
        status, body = self.harness.get("/api/estimate?lens_mm=abc&framing=full-body")
        self.assert_error(status, body, 400, "invalid_shot")

    def test_create_invalid_lens(self):
        status, body = self.harness.post("/api/shots", {"lens_mm": "abc"})
        self.assert_error(status, body, 400, "invalid_shot")

    def test_media_unknown_shot(self):
        status, body = self.harness.get("/media/nope/before.mp4")
        self.assert_error(status, body, 404, "not_found")


class ErrorFormatGenericTest(ErrorFormatTest):
    """Same setup and assert_error as ErrorFormatTest, for generic router errors."""

    test_get_unknown_shot = None
    test_delete_unknown_shot = None
    test_cancel_unknown_shot = None
    test_reapply_unknown_shot = None
    test_estimate_invalid_lens = None
    test_create_invalid_lens = None
    test_media_unknown_shot = None

    def test_unknown_api_path(self):
        status, body = self.harness.get("/api/nope")
        self.assert_error(status, body, 404, "not_found")

    def test_wrong_method(self):
        status, body = self.harness.post("/api/options", {})
        self.assert_error(status, body, 405, "method_not_allowed")


if __name__ == "__main__":
    unittest.main()
