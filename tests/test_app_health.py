import asyncio
import socket
import time
import unittest

from aiohttp import web

from app.comfy_health import check_health


class HealthTest(unittest.IsolatedAsyncioTestCase):
    async def test_reachable(self):
        async def stats(request):
            return web.json_response({"devices": [{"name": "RTX Test"}]})

        app = web.Application()
        app.router.add_get("/system_stats", stats)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            url = f"http://127.0.0.1:{port}/"
            result = await check_health(url)
        finally:
            await runner.cleanup()
        self.assertEqual(
            result,
            {"url": url, "reachable": True, "device": "RTX Test", "message": None},
        )

    async def test_unreachable(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        start = time.monotonic()
        result = await check_health(url)
        self.assertLess(time.monotonic() - start, 5)
        self.assertFalse(result["reachable"])
        self.assertIsNone(result["device"])
        self.assertEqual(
            result["message"],
            f"Can't reach ComfyUI at {url}. Start ComfyUI, then retry.",
        )

    async def test_busy(self):
        async def stats(request):
            await asyncio.sleep(30)

        app = web.Application()
        app.router.add_get("/system_stats", stats)
        runner = web.AppRunner(app, shutdown_timeout=0.1)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            url = f"http://127.0.0.1:{port}/"
            start = time.monotonic()
            result = await check_health(url)
            elapsed = time.monotonic() - start
        finally:
            await runner.cleanup()
        self.assertLess(elapsed, 6.5)
        self.assertTrue(result["reachable"])
        self.assertIsNone(result["device"])
        self.assertEqual(result["message"], "ComfyUI is busy and answered slowly.")


if __name__ == "__main__":
    unittest.main()
