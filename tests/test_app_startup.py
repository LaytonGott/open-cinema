import time
import unittest

from tests.app_harness import AppHarness

FAKE_DEVICE = "fake cuda:0 NVIDIA GeForce RTX 3090"


class AppStartupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = AppHarness().start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()

    def tearDown(self):
        if self.harness.fake._thread is None:
            self.harness.fake.start()

    def test_health_reachable(self):
        status, body = self.harness.get("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["comfyui"]["reachable"])
        self.assertEqual(body["comfyui"]["device"], FAKE_DEVICE)

    def test_health_unreachable_then_recovery(self):
        h = self.harness
        h.fake.stop()
        started = time.time()
        status, body = h.get("/api/health")
        elapsed = time.time() - started
        self.assertEqual(status, 200)
        self.assertLess(elapsed, 1.5)
        comfy = body["comfyui"]
        self.assertFalse(comfy["reachable"])
        self.assertIsNone(comfy["device"])
        self.assertEqual(comfy["message"], f"Can't reach ComfyUI at {h.fake.url}. Start ComfyUI, then retry.")

        h.fake.start()
        deadline = time.time() + 15
        reachable = False
        while time.time() < deadline:
            _, body = h.get("/api/health")
            reachable = body["comfyui"]["reachable"]
            if reachable:
                break
            time.sleep(0.1)
        self.assertTrue(reachable)

    def test_index_page(self):
        status, body = self.harness.get("/")
        self.assertEqual(status, 200)
        text = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        self.assertIn("<title>Open Cinema</title>", text)


if __name__ == "__main__":
    unittest.main()
