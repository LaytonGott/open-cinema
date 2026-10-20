import asyncio
import socket
import tempfile
import time
import unittest

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from app.server import RUNNER, create_app

VALID_SHOT = {
    "description": "A woman walks along a rainy street",
    "camera": "static",
    "lens_mm": 50,
    "aperture": 2.8,
    "framing": "waist-up",
}


class ServerTest(unittest.IsolatedAsyncioTestCase):
    async def _client(self, comfyui_url):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        client = TestClient(TestServer(create_app(comfyui_url, tmp.name)))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return client

    async def test_health_reachable(self):
        async def stats(request):
            return web.json_response({"devices": [{"name": "RTX Test"}]})

        fake = web.Application()
        fake.router.add_get("/system_stats", stats)
        fake_server = TestServer(fake)
        await fake_server.start_server()
        self.addAsyncCleanup(fake_server.close)
        url = f"http://127.0.0.1:{fake_server.port}"
        client = await self._client(url)
        resp = await client.get("/api/health")
        self.assertEqual(resp.status, 200)
        body = await resp.json()
        self.assertEqual(body["app"], "ok")
        self.assertTrue(body["comfyui"]["reachable"])
        self.assertEqual(body["comfyui"]["device"], "RTX Test")

    async def test_health_unreachable(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        client = await self._client(url)
        start = time.monotonic()
        resp = await client.get("/api/health")
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(resp.status, 200)
        body = await resp.json()
        self.assertFalse(body["comfyui"]["reachable"])
        self.assertIsNone(body["comfyui"]["device"])
        self.assertEqual(
            body["comfyui"]["message"],
            f"Can't reach ComfyUI at {url}. Start ComfyUI, then retry.",
        )

    async def test_index(self):
        client = await self._client("http://127.0.0.1:1")
        resp = await client.get("/")
        self.assertEqual(resp.status, 200)
        self.assertIn("<title>Open Cinema</title>", await resp.text())
        resp = await client.get("/static/index.html")
        self.assertEqual(resp.status, 200)

    async def test_create_shot_unreachable_comfy_gives_503(self):
        client = await self._client("http://127.0.0.1:1")
        runner = client.server.app[RUNNER]
        resp = await client.post("/api/shots", json=VALID_SHOT)
        self.assertEqual(resp.status, 503)
        self.assertEqual((await resp.json())["error"]["code"], "comfy_unreachable")
        self.assertEqual(runner.queue.qsize(), 0)
        resp = await client.get("/api/shots")
        self.assertEqual((await resp.json())["shots"], [])

    async def test_create_shot_enqueues_on_runner(self):
        async def stats(request):
            return web.json_response({"devices": [{"name": "RTX Test"}]})

        fake = web.Application()
        fake.router.add_get("/system_stats", stats)
        fake_server = TestServer(fake)
        await fake_server.start_server()
        self.addAsyncCleanup(fake_server.close)
        client = await self._client(f"http://127.0.0.1:{fake_server.port}")
        runner = client.server.app[RUNNER]
        self.assertIsNotNone(runner.task)
        ran = []

        async def record_run(shot_id):
            ran.append(shot_id)

        runner.run_shot = record_run
        resp = await client.post("/api/shots", json=VALID_SHOT)
        self.assertEqual(resp.status, 201)
        shot_id = (await resp.json())["id"]
        await asyncio.wait_for(runner.queue.join(), 5)
        self.assertEqual(ran, [shot_id])

    async def test_runner_stops_on_cleanup(self):
        client = await self._client("http://127.0.0.1:1")
        runner = client.server.app[RUNNER]
        task = runner.task
        await client.close()
        self.assertIsNone(runner.task)
        self.assertTrue(task.done())


if __name__ == "__main__":
    unittest.main()
