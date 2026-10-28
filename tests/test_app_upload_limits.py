import json
import unittest
import urllib.error
import urllib.request

from app.store import SAMPLES_DIR
from tests.app_harness import AppHarness
from tests.fake_comfy import FakeComfy

CLIP = SAMPLES_DIR / "sample-red-coat" / "before.mp4"
FORM = [("lens_mm", "50", None), ("aperture", "2.8", None), ("framing", "waist-up", None), ("name", "my clip", None)]


def upload_parts(harness, parts):
    """POST a multipart form of (name, value, filename) parts to /api/shots/import; return (status, parsed JSON).

    A part with a filename is sent as a video file (value is bytes); the others are text fields.
    """
    boundary = "----opencinema"
    body = b""
    for name, value, filename in parts:
        if filename is None:
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        else:
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                     "Content-Type: video/mp4\r\n\r\n").encode() + value + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        harness.url + "/api/shots/import", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


class UploadLimitsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def assert_refused(self, parts, field, message=None):
        h = self.harness
        before = h.get("/api/shots")[1]
        status, body = upload_parts(h, parts)
        self.assertEqual((status, body["error"]["code"], body["error"]["field"]), (400, "invalid_shot", field), body)
        if message is not None:
            self.assertEqual(body["error"]["message"], message)
        self.assertEqual(list(h.data_dir.rglob(".import-*")), [])
        self.assertEqual(h.get("/api/shots")[1], before)

    def test_two_file_parts_are_refused(self):
        self.harness.reset()
        data = CLIP.read_bytes()
        parts = [*FORM, ("file", data, "a.mp4"), ("file", data, "b.mp4")]
        self.assert_refused(parts, "file", "Send one video file.")

    def test_more_than_ten_parts_are_refused(self):
        self.harness.reset()
        extra = [(f"extra{i}", "x", None) for i in range(8)]
        parts = [*FORM, *extra, ("file", CLIP.read_bytes(), "clip.mp4")]
        self.assert_refused(parts, None)

    def test_long_text_field_is_refused(self):
        self.harness.reset()
        parts = [*[p for p in FORM if p[0] != "name"], ("name", "n" * 5000, None), ("file", CLIP.read_bytes(), "clip.mp4")]
        self.assert_refused(parts, "name")

    def test_normal_upload_is_accepted(self):
        self.harness.reset()
        status, record = upload_parts(self.harness, [*FORM, ("file", CLIP.read_bytes(), "clip.mp4")])
        self.assertEqual(status, 202, record)


if __name__ == "__main__":
    unittest.main()
