import asyncio
import threading
import unittest

from app.proxy import start_proxy, stop_proxy
from tests.app_harness import AppHarness
from tests.fake_comfy import FakeComfy


class AppProxyUrlTest(unittest.TestCase):
    def setUp(self):
        self.harness = None
        self.runner = None
        self.fake = FakeComfy()
        self.fake.start()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        if self.harness is not None:
            self.harness.stop()
        if self.runner is not None:
            asyncio.run_coroutine_threadsafe(stop_proxy(self.runner), self.loop).result(10)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(10)
        self.loop.close()
        self.fake.close()

    def test_proxy_url_used(self):
        self.runner, proxy_url = asyncio.run_coroutine_threadsafe(start_proxy(self.fake.url), self.loop).result(20)
        self.harness = AppHarness(fake=self.fake, extra_args=["--proxy-url", proxy_url])
        self.harness.start()
        status, body = self.harness.get("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["comfyui"]["reachable"])


if __name__ == "__main__":
    unittest.main()
