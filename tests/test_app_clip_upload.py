import json
import unittest
import urllib.error
import urllib.request

from app.store import SAMPLES_DIR
from tests.app_harness import AppHarness
from tests.fake_comfy import FakeComfy

CLIP = SAMPLES_DIR / "sample-red-coat" / "before.mp4"
GENERATION = ("SamplerCustomAdvanced", "VAEDecodeTiled")
FORM = {"lens_mm": "50", "aperture": "2.8", "framing": "waist-up", "name": "my clip"}


def upload(harness, fields, filename="clip.mp4", send_file=True):
    """POST a multipart form to /api/shots/import; return (status, parsed JSON)."""
    boundary = "----opencinema"
    body = b""
    for key, value in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    if send_file:
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                 "Content-Type: video/mp4\r\n\r\n").encode() + CLIP.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        harness.url + "/api/shots/import", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


class ClipUploadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_upload_runs_only_the_optics(self):
        h, fake = self.harness, self.fake
        generated = {c: fake.count(c) for c in GENERATION}
        status, record = upload(h, FORM)
        self.assertEqual(status, 202, record)
        self.assertEqual(record["status"], "optics")
        self.assertEqual(record["params"]["description"], "Imported clip: my clip")
        self.assertTrue(record["before_url"].endswith("/before.mp4"))
        done = h.wait_for_shot(record["id"], "done")
        self.assertEqual([v["aperture"] for v in done["versions"]], [2.8])
        self.assertEqual({c: fake.count(c) for c in GENERATION}, generated)
        status, _ = h.post(f"/api/shots/{record['id']}/reapply", {"aperture": 1.4})
        self.assertEqual(status, 202)
        finished = h.wait_until(record["id"], lambda s: s["status"] == "done" and len(s["versions"]) == 2,
                                what="a second version")
        self.assertEqual([v["aperture"] for v in finished["versions"]], [2.8, 1.4])

    def test_video_is_served_back(self):
        status, record = upload(self.harness, FORM)
        self.assertEqual(status, 202)
        with urllib.request.urlopen(self.harness.url + record["before_url"], timeout=15) as response:
            self.assertEqual(response.read(), CLIP.read_bytes())

    def test_bad_requests(self):
        h = self.harness
        status, body = upload(h, FORM, filename="clip.avi")
        self.assertEqual((status, body["error"]["code"], body["error"]["field"]), (400, "invalid_shot", "file"))
        status, body = upload(h, FORM, send_file=False)
        self.assertEqual((status, body["error"]["field"]), (400, "file"))
        status, body = upload(h, {**FORM, "lens_mm": "70"})
        self.assertEqual((status, body["error"]["field"]), (400, "lens_mm"))
        status, body = upload(h, {**FORM, "aperture": "3"})
        self.assertEqual((status, body["error"]["field"]), (400, "aperture"))
        status, body = upload(h, {**FORM, "framing": "tiny"})
        self.assertEqual((status, body["error"]["field"]), (400, "framing"))
        status, body = upload(h, {**FORM, "lens_mm": "wide"})
        self.assertEqual(status, 400)
        status, body = h.post("/api/shots/import", {"a": 1})
        self.assertEqual((status, body["error"]["code"]), (400, "invalid_shot"))

    def test_name_defaults_to_the_file_name(self):
        form = {k: v for k, v in FORM.items() if k != "name"}
        status, record = upload(self.harness, form, filename="Beach Walk.webm")
        self.assertEqual(status, 202)
        self.assertEqual(record["params"]["description"], "Imported clip: Beach Walk")
        self.assertTrue(record["before_url"].endswith("/before.webm"))


if __name__ == "__main__":
    unittest.main()
