import tempfile
import unittest

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from app.server import create_app, error_middleware, error_response


class ErrorsTest(unittest.IsolatedAsyncioTestCase):
    async def _client(self, app=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = app or create_app("http://127.0.0.1:1", tmp.name)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return client

    async def test_unknown_api_route_is_json_404(self):
        client = await self._client()
        resp = await client.get("/api/nope")
        self.assertEqual(resp.status, 404)
        text = await resp.text()
        self.assertNotIn("Traceback", text)
        error = (await resp.json())["error"]
        self.assertEqual(error["code"], "not_found")
        self.assertEqual(error["message"], "Nothing exists at /api/nope.")

    async def test_missing_static_file_is_json_404(self):
        client = await self._client()
        resp = await client.get("/static/missing.js")
        self.assertEqual(resp.status, 404)
        self.assertEqual((await resp.json())["error"]["code"], "not_found")

    async def test_wrong_method_is_json_405(self):
        client = await self._client()
        resp = await client.post("/api/health")
        self.assertEqual(resp.status, 405)
        self.assertEqual((await resp.json())["error"]["code"], "method_not_allowed")

    async def test_unexpected_exception_is_json_500_without_traceback(self):
        async def boom(request):
            raise RuntimeError("secret detail")

        app = web.Application(middlewares=[error_middleware])
        app.router.add_get("/boom", boom)
        client = await self._client(app)
        with self.assertLogs("app", level="ERROR"):
            resp = await client.get("/boom")
        self.assertEqual(resp.status, 500)
        text = await resp.text()
        self.assertNotIn("Traceback", text)
        self.assertNotIn("secret detail", text)
        self.assertEqual((await resp.json())["error"]["code"], "internal")

    def test_error_response_shape(self):
        resp = error_response(400, "bad", "Bad.", field="x")
        self.assertEqual(resp.status, 400)
        self.assertIn(b'"field": "x"', resp.body)

    async def test_index_still_works(self):
        client = await self._client()
        self.assertEqual((await client.get("/")).status, 200)
