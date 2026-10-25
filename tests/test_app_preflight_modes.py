import asyncio
import socket
import unittest

from aiohttp import web

from app import preflight


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
