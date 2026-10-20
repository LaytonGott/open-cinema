import asyncio
import os
import unittest
from pathlib import Path
from urllib.parse import urlparse

from app.proxy import start_proxy, stop_proxy, use_proxy


class ProxyTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_and_stop(self):
        runner, url = await start_proxy("http://127.0.0.1:9")
        stopped = False
        try:
            parts = urlparse(url)
            self.assertEqual(parts.hostname, "127.0.0.1")
            self.assertGreater(parts.port, 0)
            _, writer = await asyncio.open_connection(parts.hostname, parts.port)
            writer.close()
            await writer.wait_closed()
            await stop_proxy(runner)
            stopped = True
            with self.assertRaises(OSError):
                await asyncio.open_connection(parts.hostname, parts.port)
        finally:
            if not stopped:
                await stop_proxy(runner)

    def test_use_proxy_sets_env(self):
        old = os.environ.get("COMFY_BASE_URL")
        try:
            use_proxy("http://127.0.0.1:1234")
            self.assertEqual(os.environ["COMFY_BASE_URL"], "http://127.0.0.1:1234")
        finally:
            if old is None:
                os.environ.pop("COMFY_BASE_URL", None)
            else:
                os.environ["COMFY_BASE_URL"] = old

    def test_source_has_no_child_processes(self):
        source = (Path(__file__).parent.parent / "app" / "proxy.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.system", source)


if __name__ == "__main__":
    unittest.main()
