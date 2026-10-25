import asyncio
import socket
import unittest

from aiohttp import web

from app import preflight
from tests.app_harness import SHOT, AppHarness
from tests.fake_comfy import FakeComfy


async def _serve(handler):
    """Start a tiny aiohttp server on an ephemeral port; return (runner, base_url)."""
    app = web.Application()
    app.router.add_get("/object_info/{name}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


async def _missing(handler):
    runner, url = await _serve(handler)
    try:
        return await preflight.missing_nodes(url, ["DA3Inference"])
    finally:
        await runner.cleanup()


class PreflightModesTest(unittest.TestCase):
    def test_404_is_missing(self):
        async def handler(request):
            return web.Response(status=404)

        self.assertEqual(asyncio.run(_missing(handler)), ["DA3Inference"])

    def test_empty_answer_is_missing(self):
        async def handler(request):
            return web.json_response({})

        self.assertEqual(asyncio.run(_missing(handler)), ["DA3Inference"])

    def test_other_class_in_answer_is_missing(self):
        async def handler(request):
            return web.json_response({"LoadDA3Model": {}})

        self.assertEqual(asyncio.run(_missing(handler)), ["DA3Inference"])

    def test_listed_class_is_not_missing(self):
        async def handler(request):
            return web.json_response({request.match_info["name"]: {"input": {}}})

        self.assertEqual(asyncio.run(_missing(handler)), [])

    def test_unreachable_server_raises(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        with self.assertRaises(preflight.ObjectInfoUnreachable):
            asyncio.run(preflight.missing_nodes(f"http://127.0.0.1:{port}", ["DA3Inference"]))


class CreateShotComfyStoppedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()
        cls.fake.stop()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_create_shot_503_and_no_shot_when_comfy_stopped(self):
        status, before = self.harness.get("/api/shots")
        self.assertEqual(status, 200)
        status, body = self.harness.post("/api/shots", SHOT)
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "comfy_unreachable")
        status, after = self.harness.get("/api/shots")
        self.assertEqual(status, 200)
        self.assertEqual(after["shots"], before["shots"])
        self.assertEqual(after["shots"], [])


class ReapplyNodeMissingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeComfy()
        cls.harness = AppHarness(fake=cls.fake).start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        cls.fake.close()

    def test_reapply_refused_when_optics_node_missing_and_shot_unchanged(self):
        h = self.harness
        h.reset()
        status, created = h.post("/api/shots", {**SHOT, "aperture": 2.8})
        self.assertEqual(status, 201)
        sid = created["id"]
        h.wait_for_shot(sid, "done")
        status, snapshot = h.get(f"/api/shots/{sid}")
        self.assertEqual(status, 200)
        self.fake.remove_node("OpenOptics_DepthOfField")
        status, body = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "comfy_nodes_missing")
        self.assertTrue(body["error"]["message"].startswith("ComfyUI is missing these nodes"))
        self.assertIn("OpenOptics_DepthOfField", body["error"]["message"])
        status, after = h.get(f"/api/shots/{sid}")
        self.assertEqual(status, 200)
        for key in ("versions", "current_version", "status", "message", "progress", "error", "before_url"):
            self.assertEqual(after.get(key), snapshot.get(key), key)
